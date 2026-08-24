(function () {
  var navToggle = document.getElementById("navToggle");
  var sidebar = document.getElementById("appSidebar");
  if (navToggle && sidebar) {
    navToggle.addEventListener("click", function () {
      sidebar.classList.toggle("is-open");
    });
  }

  document.querySelectorAll("[data-confirm]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      if (!window.confirm(button.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });
})();
