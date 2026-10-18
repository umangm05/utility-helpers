// Utility Helpers — tiny progressive-enhancement helpers. No framework, no CDN.
(function () {
  "use strict";

  // Copy a string to the clipboard; returns a Promise<boolean>.
  window.uhCopy = function (text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; },
        function () { return false; });
    }
    // Fallback for non-secure contexts (e.g. plain http:// on a LAN).
    try {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.top = "-1000px";
      document.body.appendChild(ta);
      ta.select();
      var ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return Promise.resolve(ok);
    } catch (e) {
      return Promise.resolve(false);
    }
  };

  // Stamp the current year into any [data-year] node.
  document.addEventListener("DOMContentLoaded", function () {
    var y = String(new Date().getFullYear());
    var nodes = document.querySelectorAll("[data-year]");
    for (var i = 0; i < nodes.length; i++) { nodes[i].textContent = y; }
  });
})();
