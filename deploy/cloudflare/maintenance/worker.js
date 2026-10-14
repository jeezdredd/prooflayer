const DOWN_STATUSES = new Set([502, 504, 520, 521, 522, 523, 524, 525, 526, 530]);
const RETRY_SECONDS = 60;

const COPY = {
  en: {
    lang: "en",
    title: "ProofLayer is being updated",
    badge: "Maintenance",
    heading: "We are updating the system",
    body: "ProofLayer is temporarily unavailable while we roll out changes. Your files and results are safe. This page will reload by itself as soon as we are back.",
    retry: "Checking again in",
    seconds: "s",
    contact: "Questions:",
  },
  ru: {
    lang: "ru",
    title: "ProofLayer обновляется",
    badge: "Технические работы",
    heading: "Мы обновляем систему",
    body: "ProofLayer временно недоступен, пока мы выкатываем изменения. Ваши файлы и результаты в сохранности. Страница обновится сама, как только мы вернёмся.",
    retry: "Повторная проверка через",
    seconds: " с",
    contact: "Вопросы:",
  },
};

export function pickLang(request) {
  const header = (request.headers.get("Accept-Language") || "").toLowerCase();
  const first = header.split(",").map((part) => part.trim().slice(0, 2)).find(Boolean);
  return first === "ru" || first === "kk" || first === "uk" || first === "be" ? "ru" : "en";
}

export function isApi(request) {
  return new URL(request.url).hostname.startsWith("api.");
}

export function maintenancePage(lang) {
  const c = COPY[lang];
  return `<!doctype html>
<html lang="${c.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${c.title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px 16px; background: #050608; color: #e4e8f3; font-family: "IBM Plex Sans", system-ui, -apple-system, sans-serif; }
.glow { position: fixed; inset: 0; pointer-events: none; background: radial-gradient(600px 300px at 50% 0%, rgba(167,139,250,0.14), transparent 70%); }
main { position: relative; width: 100%; max-width: 520px; }
.logo { font-family: "Instrument Serif", Georgia, serif; font-size: 34px; margin-bottom: 28px; }
.logo i { background: linear-gradient(120deg, #a78bfa, #22d3ee, #f5b042); -webkit-background-clip: text; background-clip: text; color: transparent; }
.card { border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.02); border-radius: 14px; padding: 32px 28px; }
.badge { display: inline-flex; align-items: center; gap: 8px; font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 10px; letter-spacing: 0.18em; text-transform: uppercase; color: #f5b042; border: 1px solid rgba(245,176,66,0.35); border-radius: 999px; padding: 5px 11px; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: #f5b042; animation: pulse 1.6s ease-in-out infinite; }
h1 { font-family: "Instrument Serif", Georgia, serif; font-weight: 400; font-size: 40px; line-height: 1.15; margin: 20px 0 12px; }
p { margin: 0; color: #8d96b3; line-height: 1.6; font-size: 15px; }
.meta { margin-top: 24px; font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 11px; letter-spacing: 0.08em; color: #5d6783; }
a { color: #a78bfa; text-decoration: none; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
</style>
</head>
<body>
<div class="glow"></div>
<main>
<div class="logo">Proof<i>Layer</i></div>
<div class="card">
<span class="badge"><span class="dot"></span>${c.badge}</span>
<h1>${c.heading}</h1>
<p>${c.body}</p>
<div class="meta">${c.retry} <span id="t">${RETRY_SECONDS}</span>${c.seconds} · ${c.contact} <a href="mailto:support@prooflayer.cloud">support@prooflayer.cloud</a></div>
</div>
</main>
<script>
let left = ${RETRY_SECONDS};
const el = document.getElementById("t");
setInterval(() => { left -= 1; if (left <= 0) location.reload(); else el.textContent = left; }, 1000);
</script>
</body>
</html>`;
}

export function maintenanceResponse(request) {
  const lang = pickLang(request);
  const headers = { "Retry-After": String(RETRY_SECONDS), "Cache-Control": "no-store" };
  if (isApi(request)) {
    const body = JSON.stringify({ code: "maintenance", detail: COPY[lang].body, retry_after: RETRY_SECONDS });
    return new Response(body, { status: 503, headers: { ...headers, "Content-Type": "application/json; charset=utf-8" } });
  }
  return new Response(maintenancePage(lang), { status: 503, headers: { ...headers, "Content-Type": "text/html; charset=utf-8" } });
}

export default {
  async fetch(request, env) {
    if (env && env.MAINTENANCE === "1") return maintenanceResponse(request);
    let response;
    try {
      response = await fetch(request);
    } catch (error) {
      return maintenanceResponse(request);
    }
    if (DOWN_STATUSES.has(response.status)) return maintenanceResponse(request);
    return response;
  },
};
