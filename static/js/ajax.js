(function () {
  function getCookie(name) {
    return document.cookie.split(";").map(function (item) { return item.trim(); }).reduce(function (found, item) {
      if (found) return found;
      var parts = item.split("=");
      return parts[0] === name ? decodeURIComponent(parts.slice(1).join("=")) : "";
    }, "");
  }

  window.hrmsFetch = function (url, options) {
    var opts = options || {};
    opts.headers = Object.assign({
      "X-Requested-With": "XMLHttpRequest",
      "Accept": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    }, opts.headers || {});
    return fetch(url, opts).then(function (response) {
      return response.json().then(function (payload) {
        payload.httpStatus = response.status;
        return payload;
      });
    });
  };
})();
