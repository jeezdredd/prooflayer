(function () {
  var script = document.currentScript;
  var API_BASE = (script && script.getAttribute("data-api")) || "https://prooflayer.app/api/v1";

  var VERDICT_CONFIG = {
    authentic:    { label: "Verified Authentic", color: "#16a34a", bg: "#dcfce7", icon: "\u2713" },
    fake:         { label: "Likely Fake",         color: "#dc2626", bg: "#fee2e2", icon: "\u2717" },
    suspicious:   { label: "Suspicious",          color: "#d97706", bg: "#fef3c7", icon: "!" },
    inconclusive: { label: "Inconclusive",        color: "#6b7280", bg: "#f3f4f6", icon: "?" },
    unknown:      { label: "Not in Database",     color: "#6b7280", bg: "#f3f4f6", icon: "?" },
  };

  function applyStyle(el, color, bg) {
    el.style.color = color;
    el.style.background = bg;
    el.style.borderColor = color + "40";
  }

  function renderBadge(target, sha256) {
    var el = document.createElement("div");
    el.style.cssText = "display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:6px;font-family:system-ui,-apple-system,sans-serif;font-size:13px;font-weight:600;border:1px solid;cursor:default;";
    el.textContent = "Checking ProofLayer\u2026";
    applyStyle(el, "#6b7280", "#f3f4f6");
    target.appendChild(el);

    fetch(API_BASE + "/content/widget/embed/" + encodeURIComponent(sha256) + "/", {
      headers: { "Accept": "application/json" },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var verdict = data.is_known_fake ? "fake" : (data.verdict || "unknown");
        var cfg = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.unknown;
        var score = data.score != null ? " (" + Math.round(data.score * 100) + "% fake)" : "";
        var link = data.submission_id
          ? "https://prooflayer.app/results/" + data.submission_id
          : "https://prooflayer.app";

        applyStyle(el, cfg.color, cfg.bg);
        el.innerHTML =
          "<span style='font-size:15px'>" + cfg.icon + "</span>" +
          "<span>ProofLayer: " + cfg.label + "</span>" +
          (score ? "<span style='font-weight:400;opacity:0.8'>" + score + "</span>" : "") +
          "<a href='" + link + "' target='_blank' rel='noopener' style='margin-left:4px;color:" +
          cfg.color + ";opacity:0.7;font-size:11px;text-decoration:none;'>view\u2192</a>";
      })
      .catch(function () {
        el.textContent = "ProofLayer: unavailable";
      });
  }

  function init() {
    var nodes = document.querySelectorAll("[data-prooflayer-sha256]");
    for (var i = 0; i < nodes.length; i++) {
      var sha = nodes[i].getAttribute("data-prooflayer-sha256");
      if (sha) renderBadge(nodes[i], sha);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
