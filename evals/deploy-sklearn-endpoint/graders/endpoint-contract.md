---
type: llm
---

PASS if ALL hold:
1. The prediction code is a Python function in a project file that takes the request inputs as arguments and returns a JSON-serialisable value; the endpoint is created from the Domino UI (Deployments > Endpoints) or the `/api/modelServing/v1/modelApis` API by naming that file and function.
2. The curl request posts JSON in one of the documented forms, `{"data": {...}}` with named arguments or `{"parameters": [...]}` with positional ones, to the endpoint's URL (ending in `.../latest/model` or the URL shown on the endpoint page).
3. For a restricted synchronous endpoint the call uses HTTP Basic authentication with the model access token as both username and password (for example `curl -u TOKEN:TOKEN`), or it says an unrestricted endpoint needs no token. Mentioning that Bearer is for asynchronous endpoints is fine but not required.
FAIL if it sends `Authorization: Bearer` as the way to call a synchronous restricted endpoint, describes Kubernetes HPA / scale-to-zero autoscaling, or claims the endpoint image installs the project's requirements.txt (Domino endpoint images do not read requirements.txt; packages come from the environment's Dockerfile instructions).
