---
type: service
created: 2026-06-17
source: extension/
---

# Browser Extension

Manifest V3 extension for Chrome and Firefox. Right-click any image -> "Verify with ProofLayer" -> popup shows verdict.

## Project layout

```
extension/
  manifest.json           Chrome MV3 (background.service_worker)
  manifest.firefox.json   Firefox MV3 (background.scripts array)
  vite.config.ts          @crxjs/vite-plugin, mode=firefox -> dist-firefox
  package.json
  assets/                 icon16/32/48/128.png
  src/
    background/sw.ts      service worker: context menu, ANALYZE_URL handler
    content/inject.ts     hover detection, stores srcUrl to storage
    popup/
      popup.html
      popup.ts            poll loop, renderResult, show()
      popup.css           freq-bar animation, verdict badges
```

## Build

```bash
cd extension
npm install
npm run build              # Chrome -> dist-chrome/
npm run build:firefox      # Firefox -> dist-firefox/
```

Chrome: load `dist-chrome/` as unpacked extension.
Firefox: `about:debugging` -> "This Firefox" -> Load Temporary Add-on -> pick `dist-firefox/manifest.json`.

## Flow

1. Content script (`inject.ts`) listens for `mouseover` on `<img>` tags, stores `srcUrl` to `chrome.storage.local`.
2. Service worker (`sw.ts`) creates context menu item "Verify with ProofLayer" on install.
3. User right-clicks image -> `contextMenus.onClicked` fires.
4. SW posts `{url}` to `POST /api/v1/content/analyze-url/`.
5. Result `{submission_id}` stored in `pl_pending_result`, popup opened via `chrome.action.openPopup()`.
6. Popup (`popup.ts`) reads `pl_pending_result`, starts polling `GET /api/v1/content/submissions/{id}/status/` every 2s (max 60 attempts).
7. On `status=completed` -> renders verdict badge + confidence bar + link to `prooflayer.cloud/result/{id}`.

## API endpoints used

| Endpoint | Auth |
|----------|------|
| `POST /api/v1/content/analyze-url/` | optional JWT or anonymous (5/day per IP) |
| `GET /api/v1/content/submissions/{id}/status/` | none (AllowAny) |

## Anonymous quota

`AnonymousQuota` model: `ip` + `date` unique together. `count` incremented atomically via `select_for_update()` + `IntegrityError` catch. Limit = 5/day. Returns 429 `{error: "anonymous_limit_reached"}` when exceeded. Popup shows "limit" state with login CTA.

## Known limitations

- `data:` URL images (e.g. Google Images inline thumbnails) are unsupported - shown as error message in popup.
- `chrome.action.openPopup()` not supported in Firefox - popup must be opened manually after right-click.
- Login flow (btn-login opens `prooflayer.cloud/login`) does not yet persist JWT back to extension storage after OAuth/login completes.

## Gotchas

- Firefox: `background.service_worker` disabled -> use `manifest.firefox.json` with `background.scripts`.
- Context menu: must call `contextMenus.removeAll()` before `create` on SW restart or duplicate ID error.
- CSS hidden states: ID selector specificity overrides `[hidden]` attribute. Fix: `[hidden] { display: none !important; }` at top of popup.css.
- SW cannot `sendMessage` to itself - must call `analyzeUrl()` directly from `onClicked` listener.

## See also

- [[api/endpoints]]
- [[models/AnonymousQuota]]
