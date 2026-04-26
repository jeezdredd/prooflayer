(function () {
  var API_BASE = "http://localhost:8000/api/v1";

  var VERDICT_CONFIG = {
    authentic:    { label: "Verified Authentic", color: "#16a34a", bg: "#dcfce7", icon: "✓" },
    fake:         { label: "Likely Fake",         color: "#dc2626", bg: "#fee2e2", icon: "✗" },
    suspicious:   { label: "Suspicious",          color: "#d97706", bg: "#fef3c7", icon: "!" },
    inconclusive: { label: "Inconclusive",        color: "#6b7280", bg: "#f3f4f6", icon: "?" },
  };

  function createBadge(submissionId, target) {
    var el = document.createElement("div");
    el.style.cssText = "display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:6px;font-family:system-ui,sans-serif;font-size:13px;font-weight:600;border:1px solid;cursor:default;";
    el.textContent = "Checking…";
    el.style.color = "#6b7280";
    el.style.background = "#f3f4f6";
    el.style.borderColor = "#e5e7eb";
    target.appendChild(el);

    fetch(API_BASE + "/content/submissions/" + submissionId + "/", {
      headers: { "Accept": "application/json" }
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var cfg = VERDICT_CONFIG[data.final_verdict] || VERDICT_CONFIG.inconclusive;
        var score = data.final_score != null ? Math.round(data.final_score * 100) + "% fake" : "";
        el.style.color = cfg.color;
        el.style.background = cfg.bg;
        el.style.borderColor = cfg.color + "40";
        el.innerHTML =
          "<span style='font-size:15px'>" + cfg.icon + "</span>" +
          "<span>ProofLayer: " + cfg.label + "</span>" +
          (score ? "<span style='font-weight:400;opacity:0.8'>(" + score + ")</span>" : "") +
          "<a href='https://prooflayer.app' target='_blank' rel='noopener' style='margin-left:4px;color:" + cfg.color + ";opacity:0.6;font-size:11px;text-decoration:none;'>↗</a>";
      })
      .catch(function () {
        el.textContent = "ProofLayer: unavailable";
      });
  }

  function init() {
    var nodes = document.querySelectorAll("[data-prooflayer-id]");
    for (var i = 0; i < nodes.length; i++) {
      var id = nodes[i].getAttribute("data-prooflayer-id");
      if (id) createBadge(id, nodes[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
