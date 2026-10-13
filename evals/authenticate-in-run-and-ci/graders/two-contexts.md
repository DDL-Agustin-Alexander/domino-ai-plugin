---
type: llm
---

PASS if the reply distinguishes the two contexts correctly:
- Inside a Domino run: call `$DOMINO_API_PROXY/<path>` with no Authorization header, or fetch a short-lived token from `http://localhost:8899/access-token` and send it as `Authorization: Bearer`.
- Outside Domino (CI): use a Personal Access Token or a Domino service-account token as `Authorization: Bearer` against the deployment's public URL.
FAIL if it recommends the legacy API key (`X-Domino-Api-Key`, `DOMINO_USER_API_KEY`) for either context, or tells the user to derive the host from a JWT claim.
