---
type: llm
---

PASS if the reply explains that the app calls the Domino API through `$DOMINO_API_PROXY` with no auth header, fetches a bearer token from `http://localhost:8899/access-token` per request, or forwards the viewer's `Authorization` header that Domino's identity propagation supplies, that its own asset and API URLs are relative (not root-absolute) so they survive Domino's proxy path prefix, and that it is served on host 0.0.0.0 port 8888 from app.sh.
FAIL if it uses an API key, tells the browser to fetch root-absolute `/api/...` paths, or binds to localhost.
