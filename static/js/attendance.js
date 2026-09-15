(function () {
  var form = document.querySelector("[data-attendance-form]");
  var timer = document.getElementById("workingTimer");
  var statusLabel = document.getElementById("attendanceStatus");
  var breakTime = document.getElementById("breakTime");
  var historyBody = document.getElementById("attendanceSessions");
  var messageBox = document.getElementById("attendanceMessage");
  var attendanceUrl = form ? form.dataset.attendanceUrl : "";
  var stateUrl = form ? form.dataset.stateUrl : "";
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

  function showError(error) {
    if (error && error.network) {
      showMessage({ success: false, message: "Unable to connect to the server. Your attendance was not confirmed." });
      return;
    }
    var payload = error && error.payload;
    var message = payload && payload.message ? payload.message : (error && error.message ? error.message : "We couldn't complete your attendance request. Please try again.");
    if (error && error.httpStatus && (!payload || !payload.message)) {
      message += " (Server returned " + error.httpStatus + " for " + (error.requestUrl || "the attendance endpoint") + ".)";
    }
    showMessage({ success: false, message: message });
  }

  function renderState(data) {
    if (!data) return;
    activeStart = data.active_started_at || "";
    baseSeconds = Number.isFinite(Number(data.working_seconds)) ? Number(data.working_seconds) : parseDuration(data.working_time || "00:00:00");
    serverNow = Date.parse(data.server_now || "");
    clientStart = Date.now();
    if (breakTime) breakTime.textContent = data.break_time || "00:00:00";
    if (statusLabel) {
      var state = data.state || (data.is_working ? "WORKING" : (data.is_on_break ? "ON_BREAK" : (data.is_complete ? "COMPLETED" : "NOT_STARTED")));
      statusLabel.textContent = state === "ON_BREAK" ? "ON BREAK" : state;
      statusLabel.className = state === "WORKING" ? "badge present" : (state === "ON_BREAK" ? "badge warning" : "badge draft");
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
      if (!attendanceUrl || attendanceUrl.indexOf("[object") !== -1) {
        showMessage({ success: false, message: "Attendance endpoint is unavailable. Refresh the page and try again." });
        return;
      }
      var data = new FormData(form);
      data.set(submitter.name, submitter.value);
      submitter.disabled = true;
      var originalLabel = submitter.textContent;
      submitter.textContent = "Processing...";
      window.hrmsFetch(attendanceUrl, { method: "POST", body: data }).then(function (payload) {
        showMessage(payload);
        renderState(payload.data);
        window.setTimeout(function () { window.location.reload(); }, 250);
      }).catch(function (error) {
        showError(error);
        if (window.hrmsFetch && stateUrl) {
          window.hrmsFetch(stateUrl, { method: "GET" }).then(function (payload) {
            renderState(payload.data);
          }).catch(function () {});
        }
      }).finally(function () {
        submitter.disabled = false;
        submitter.textContent = originalLabel;
      });
    });
  }
})();
