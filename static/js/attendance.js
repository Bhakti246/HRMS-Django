(function () {
  var form = document.querySelector("[data-attendance-form]");
  var timer = document.getElementById("workingTimer");
  var statusLabel = document.getElementById("attendanceStatus");
  var breakTime = document.getElementById("breakTime");
  var historyBody = document.getElementById("attendanceSessions");
  var messageBox = document.getElementById("attendanceMessage");
  var activeStart = timer ? timer.dataset.start : "";
  var baseSeconds = timer ? parseDuration(timer.dataset.base || "00:00:00") : 0;
  var serverNow = timer ? Date.parse(timer.dataset.serverNow || "") : 0;
  var clientStart = Date.now();

  function parseDuration(value) {
    var parts = value.split(":").map(function (part) { return parseInt(part, 10) || 0; });
    return (parts[0] * 3600) + (parts[1] * 60) + parts[2];
  }

  function format(seconds) {
    seconds = Math.max(0, Math.floor(seconds));
    var h = String(Math.floor(seconds / 3600)).padStart(2, "0");
    var m = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
    var s = String(seconds % 60).padStart(2, "0");
    return h + ":" + m + ":" + s;
  }

  function tick() {
    if (!timer) return;
    var seconds = baseSeconds;
    if (activeStart && serverNow) {
      seconds += Math.floor((Date.now() - clientStart + serverNow - Date.parse(activeStart)) / 1000);
    }
    timer.textContent = format(seconds);
  }

  function showMessage(payload) {
    if (!messageBox) return;
    messageBox.textContent = payload.message || "";
    messageBox.className = payload.success ? "toast success" : "toast error";
    messageBox.hidden = false;
  }

  function renderState(data) {
    if (!data) return;
    activeStart = data.active_started_at || "";
    baseSeconds = parseDuration(data.working_time || "00:00:00");
    serverNow = Date.parse(data.server_now || "");
    clientStart = Date.now();
    if (breakTime) breakTime.textContent = data.break_time || "00:00:00";
    if (statusLabel) {
      statusLabel.textContent = data.is_working ? "WORKING" : "ON BREAK / COMPLETE";
      statusLabel.className = data.is_working ? "badge present" : "badge draft";
    }
    if (historyBody && data.sessions) {
      historyBody.innerHTML = data.sessions.length ? data.sessions.map(function (row) {
        return "<tr><td>" + row.punch_in + "</td><td>" + row.punch_out + "</td><td>" + row.duration + "</td></tr>";
      }).join("") : "<tr><td colspan=\"3\" class=\"empty\">No sessions recorded today.</td></tr>";
    }
    tick();
  }

  if (timer) {
    tick();
    window.setInterval(tick, 1000);
  }

  if (form && window.hrmsFetch) {
    form.addEventListener("submit", function (event) {
      var submitter = event.submitter;
      if (!submitter || !submitter.name) return;
      event.preventDefault();
      var data = new FormData(form);
      data.set(submitter.name, submitter.value);
      submitter.disabled = true;
      window.hrmsFetch(form.action, { method: "POST", body: data }).then(function (payload) {
        showMessage(payload);
        renderState(payload.data);
      }).catch(function () {
        showMessage({ success: false, message: "Attendance request failed. Try again." });
      }).finally(function () {
        submitter.disabled = false;
      });
    });
  }
})();
