/**
 * Smart Product Agent — lightweight UI helpers (Flask + vanilla JS).
 * - Theme toggle + localStorage
 * - Loading overlay on form submit
 * - Category chip filter + click-to-fill
 */

(function () {
  "use strict";

  var THEME_KEY = "spa-theme";

  /** Read current theme from <html data-theme>. */
  function getTheme() {
    return document.documentElement.getAttribute("data-theme") || "dark";
  }

  /** Apply theme to <html> and persist for next visit. */
  function setTheme(mode) {
    document.documentElement.setAttribute("data-theme", mode);
    try {
      localStorage.setItem(THEME_KEY, mode);
    } catch (e) {
      /* ignore private mode / blocked storage */
    }
  }

  /** Wire theme toggle button. */
  function initThemeToggle() {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;

    btn.addEventListener("click", function () {
      var next = getTheme() === "dark" ? "light" : "dark";
      setTheme(next);
    });
  }

  /** Show full-page loading state while browser waits for POST response. */
  function initLoadingOverlay() {
    var form = document.getElementById("search-form");
    var overlay = document.getElementById("loading-overlay");
    if (!form || !overlay) return;

    form.addEventListener("submit", function () {
      overlay.hidden = false;
      overlay.setAttribute("aria-hidden", "false");
    });
  }

  /** Filter category chips; clicking a chip fills the category input. */
  function initCategoryChips() {
    var filter = document.getElementById("category-filter");
    var chipsWrap = document.getElementById("category-chips");
    var categoryInput = document.getElementById("category");
    if (!chipsWrap || !categoryInput) return;

    var chips = chipsWrap.querySelectorAll(".chip");

    function applyFilter() {
      if (!filter) return;
      var q = filter.value.trim().toLowerCase();
      chips.forEach(function (chip) {
        var val = (chip.getAttribute("data-value") || "").toLowerCase();
        chip.hidden = q.length > 0 && val.indexOf(q) === -1;
      });
    }

    if (filter) {
      filter.addEventListener("input", applyFilter);
      applyFilter();
    }

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        var v = chip.getAttribute("data-value") || "";
        categoryInput.value = v;
        categoryInput.focus();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initThemeToggle();
    initLoadingOverlay();
    initCategoryChips();
  });
})();
