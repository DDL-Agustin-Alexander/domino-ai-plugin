---
type: llm
---

PASS if the script (a) authenticates with `Authorization: Bearer <token>` where the token is a Personal Access Token or a Domino service-account token read from a secret / environment variable, against the deployment's public URL; (b) creates the version with POST `/api/modelServing/v1/modelApis/{modelApiId}/versions`; and (c) polls `GET /api/modelServing/v1/modelApis/{modelApiId}` (or the version resource) until the status is Running or a failure state, rather than assuming success.
FAIL if it uses an API key header, uses `DOMINO_API_PROXY` or `localhost:8899` outside Domino, or uses a `/v4/models...` route without labelling it internal.
