---
type: llm
---

PASS if the reply recommends a Domino service-account token (or a Personal Access Token when the pipeline acts as a specific person) sent as `Authorization: Bearer <token>` against the deployment's public URL, says legacy user API keys (`X-Domino-Api-Key`) are deprecated and should not be used, treats 401 and 403 as auth or permission problems to fix rather than retry (and never suggests falling back to an API key on 403), treats 502 as a case for smaller or paginated requests with limited retries only for idempotent calls, and tells the user to page through the job list with the API's pagination parameters rather than fetching everything in one response.
FAIL if it recommends the API key, says to use `DOMINO_API_PROXY` or `localhost:8899` outside Domino, or suggests retrying 401/403 unchanged.
