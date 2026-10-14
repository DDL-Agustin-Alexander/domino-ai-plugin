---
type: llm
---

PASS if the reply identifies that `serve` is run without the `-s` (single-page application fallback) flag in app.sh, so client-side routes such as /reports are not rewritten to index.html, and proposes `npx serve -s dist -l 8888` (or an equivalent SPA fallback) as the fix. Noting that the rest of the config (base './', host 0.0.0.0, port 8888, build step) is already correct is fine.
FAIL if it misses the missing `-s` flag, or claims it already changed a file.
