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
    opts.credentials = opts.credentials || "same-origin";
    return fetch(url, opts).then(function (response) {
      return response.text().then(function (body) {
        var payload;
        try {
          payload = body ? JSON.parse(body) : {};
        } catch (error) {
          var parseError = new Error("The server returned an invalid response.");
          parseError.httpStatus = response.status;
          parseError.requestUrl = response.url || url;
          parseError.contentType = response.headers.get("content-type") || "";
          parseError.serverMessage = response.statusText || "Invalid server response";
          if (window.console && console.error) {
            console.error("HRMS attendance response was not JSON", {
              url: parseError.requestUrl,
              status: parseError.httpStatus,
              contentType: parseError.contentType
            });
          }
          throw parseError;
        }
        payload.httpStatus = response.status;
        if (!response.ok || payload.success === false) {
          var serverError = new Error(payload.message || "The attendance request was rejected.");
          serverError.httpStatus = response.status;
          serverError.payload = payload;
          throw serverError;
        }
        return payload;
      });
    }).catch(function (error) {
      if (error && (error.httpStatus || error.payload || error.serverMessage)) throw error;
      var networkError = new Error("Unable to connect to the server.");
      networkError.network = true;
      throw networkError;
    });
  };
})();
