---
type: llm
---

PASS if the API call is `POST .../remotefs/v1/snapshots` with a JSON body containing `volumeId` and the message in `description` (optionally `tagNames`), authenticated with `$DOMINO_API_PROXY` (no header) or a bearer token from `http://localhost:8899/access-token`.
FAIL if it uses a `/v4/...` route for the snapshot, an API key header, or derives the host from a JWT claim.
