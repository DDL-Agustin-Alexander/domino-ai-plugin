# Domino API integration from a FastAPI app

Call Domino APIs from the FastAPI backend, never from browser JavaScript.

## Authentication

Inside the App prefer `DOMINO_API_PROXY` with no header; otherwise fetch a short-lived token per request:

```python
import os, requests

def api_get(path: str) -> requests.Response:
    proxy = os.environ.get("DOMINO_API_PROXY")
    if proxy:
        return requests.get(f"{proxy}{path}", timeout=30)
    token = requests.get("http://localhost:8899/access-token").text.strip()
    return requests.get(f"{os.environ['DOMINO_API_HOST']}{path}",
                        headers={"Authorization": f"Bearer {token}"}, timeout=30)
```

Outside a run use a Personal Access Token or service account token as `Authorization: Bearer`. Legacy API keys (`X-Domino-Api-Key`, `DOMINO_USER_API_KEY`) are deprecated and must not be used. Reference: https://docs.domino.ai/cloud/reference/api/domino-api-authentication and the `domino-api-intro` skill (hosts, pagination limits, errors). To act as the viewer instead of the publisher, publish the App with extended identity propagation and forward the request's `Authorization` header (`domino-apps` skill).

## API base paths

| API | Path | Notes |
|---|---|---|
| Public API | `/api/...` on `$DOMINO_API_HOST`, for example `/api/jobs/beta/jobs?projectId=...` or `/api/apps/v1/apps` | Routes in https://docs.domino.ai/api-specs/cloud/public-api.json and https://docs.domino.ai/api-specs/6.3/public-api.json |
| Governance | `/api/governance/v1/...` | Base URL selection in the `domino-governance` skill (Configuration section); not always reachable on `$DOMINO_API_HOST` |
| `/v4/...` | Domino Internal API | Not in the Public API and may change between Domino versions; use only when no `/api/...` route exists and label it at the point of use |

Never derive the cluster URL from a JWT claim. Use `$DOMINO_API_HOST` in a run and the deployment's public URL outside one.

## Environment variables

`DOMINO_API_HOST`, `DOMINO_PROJECT_ID`, `DOMINO_PROJECT_NAME`, `DOMINO_PROJECT_OWNER`, `DOMINO_RUN_HOST_PATH` (URL prefix of the App). When an API call fails, show the error and name the missing variable or permission; do not fabricate data.

## Where to verify routes

Confirm every route and field in the published specs above, or in the deployment's own reference at `https://<domino-domain>/docs` (Scalar, unauthenticated; `openapi-public.json` is the full Public API, `openapi-internal.json` the `/v4` Internal API). `$DOMINO_API_HOST/assets/public-api.json` is only a subset of the Public API. Product docs: https://docs.domino.ai/cloud/reference/api/domino-open-api and https://docs.domino.ai/cloud/platform-capabilities/features/apps .
