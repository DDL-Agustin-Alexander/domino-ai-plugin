# Model serving lifecycle: worked requests

Applies to Domino 6.3 and Domino Cloud. Every route here is in both public API specs unless marked (Cloud). Read calls were verified against Domino Cloud 6.4 on 2026-10-12; field names come from the spec schemas (`ModelApiCreationRequest`, `ModelApiVersionCreationRequest`, `ModelApiUpdateRequest`, `ModelApi`, `NewRegisteredModelV2`).

## Setup

```python
import os
import time
import requests

if os.environ.get("DOMINO_API_PROXY"):                 # in a run, proxy available
    base, headers = os.environ["DOMINO_API_PROXY"], {}
else:                                                  # in a run without the proxy
    base = os.environ["DOMINO_API_HOST"]
    token = requests.get("http://localhost:8899/access-token").text.strip()
    headers = {"Authorization": f"Bearer {token}"}
# Outside Domino: base = deployment URL; headers = {"Authorization": "Bearer <PAT or service-account token>"}
```

## List and inspect

```python
r = requests.get(f"{base}/api/modelServing/v1/modelApis", headers=headers,
                 params={"projectId": os.environ["DOMINO_PROJECT_ID"], "limit": 25, "offset": 0})
r.raise_for_status()
for api in r.json()["items"]:
    active = api.get("activeVersion", {})
    print(api["id"], api["name"], api["replicas"], api["routingMode"], api["isAsync"],
          active.get("number"), active.get("deployment", {}).get("status"))
total = r.json()["metadata"]["totalCount"]
```

Filters: `projectId`, `environmentId`, `name` (regular expression), `registeredModelName` (+ `registeredModelVersion`), `limit` (default 25), `offset`, `orderBy`. Archived endpoints carry `isArchived: true`.

`GET /api/modelServing/v1/modelApis/{modelApiId}` returns the same object: `id`, `name`, `description`, `environmentId`, `hardwareTierId`, `replicas`, `routingMode` (`Basic` or advanced), `isAsync`, `strictNodeAntiAffinity`, `access{isPublic, accessTokens[]}`, `healthCheck{...}`, `overrideRequestTimeoutSecs`, `collaborators[]`, `volumes[]`, `activeVersion{id, number, dataPlaneId, deployment{status, isPending}}`, `metadata{created, createdBy, lastModified}`. On Domino Cloud `access.isPublic` is a legacy flag independent of the endpoint's visibility (`Public`, `Discoverable`, `Private`), which is read and set through `GET|PUT /api/modelServing/beta/modelApis/{modelApiId}/visibility`; collaborators there carry the roles `Owner`, `Editor`, `Operator`, `Viewer`.

Versions: `GET .../modelApis/{modelApiId}/versions` lists `ModelApiVersion` objects (`id`, `number`, `projectId`, `source`, `commitId`, `environmentRevisionId`, `predictionDatasetResourceId`, `logHttpRequestResponse`, `monitoringEnabled`, `recordInvocation`, `labels`, `metadata`).

## Create from project files

```python
body = {
    "name": "churn-scorer",
    "description": "GBM churn model",
    "environmentId": ENVIRONMENT_ID,              # GET /api/environments/beta/environments
    "hardwareTierId": TIER_ID,                    # optional; an endpoint tier, GET /api/hardwaretiers/v1/hardwaretiers
    "replicas": 2,                                # optional
    "isAsync": False,
    "strictNodeAntiAffinity": False,
    "environmentVariables": [{"key": "MODEL_PATH", "value": "models/gbm.pkl"}],
    "version": {
        "projectId": os.environ["DOMINO_PROJECT_ID"],
        "source": {"type": "File", "file": "model.py", "function": "predict", "excludeFiles": ["data/"]},
        "logHttpRequestResponse": False,
        "monitoringEnabled": False,
        # optional: "commitId": "<dfs or artifacts commit>", "environmentId": "...", "shouldDeploy": True
    },
}
r = requests.post(f"{base}/api/modelServing/v1/modelApis", headers=headers, json=body)
r.raise_for_status()                              # 201
model_api_id = r.json()["id"]
versions = requests.get(f"{base}/api/modelServing/v1/modelApis/{model_api_id}/versions", headers=headers).json()
version_id = max(versions, key=lambda v: v["number"])["id"]
wait_version_running(model_api_id, version_id)
```

## Create from a registered model

Same body with `"source": {"type": "Registry", "registeredModelName": "churn-gbm", "registeredModelVersion": 3}`. The `requirements.txt` MLflow inferred when the model was logged is installed into the image.

## Wait until a version is Running

Poll the **version**, not only the Model API: under Basic routing the previous version keeps serving (and stays `activeVersion`) until the new one is up, so `activeVersion.deployment.status` can read `Running` for the old version right after you create a new one.

```python
def wait_version_running(model_api_id, version_id, timeout_s=1800):
    """Poll one version until it is deployed and serving, then confirm it became the active version."""
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        v = requests.get(f"{base}/api/modelServing/v1/modelApis/{model_api_id}/versions/{version_id}",
                         headers=headers).json()
        deployment = v.get("deployment") or {}                 # absent until a deployment exists
        status, pending = deployment.get("status", "Pending"), deployment.get("isPending", True)
        if status != last:
            print(f"version {v.get('number')}: {status} (pending={pending})")
            last = status
        if status == "Running" and not pending:
            api = requests.get(f"{base}/api/modelServing/v1/modelApis/{model_api_id}", headers=headers).json()
            if api.get("activeVersion", {}).get("id") == version_id:
                return v
        time.sleep(15)
    raise TimeoutError(f"version {version_id} not Running after {timeout_s}s (last status: {last}); "
                       "read its build and instance logs")
```

`Running` is the documented ready state. The spec types `deployment.status` as a free string and does not enumerate the other values, so the helper prints them and keeps polling until the deadline; a status that stops changing is the cue to read the build and instance logs (below).

## Prediction URL

```python
deployment_url = os.environ["DOMINO_URL"]          # not injected by Domino: set it yourself to the deployment URL shown on the endpoint Overview tab
sync_url = f"{deployment_url}/models/{model_api_id}/latest/model"
async_url = f"{deployment_url}/api/modelApis/async/v1/{model_api_id}"
```

Sync calls use `auth=(token, token)`; async calls use `Authorization: Bearer <token>`; the token is an endpoint access token (**Settings** > **Invocation**), not your API token. Request formats are in `domino-model-endpoints`.

## New version

```python
r = requests.post(f"{base}/api/modelServing/v1/modelApis/{model_api_id}/versions", headers=headers, json={
    "projectId": os.environ["DOMINO_PROJECT_ID"],
    "source": {"type": "File", "file": "model.py", "function": "predict"},
    "logHttpRequestResponse": False,
    "monitoringEnabled": False,
    "shouldDeploy": True,                        # optional in the spec with no stated default; set it explicitly
    "description": "retrained 2026-10",
})
r.raise_for_status()
version_id = r.json()["id"]
wait_version_running(model_api_id, version_id)
```

With Basic routing, `latest` switches to the new version once it runs and the previous version shuts down. With Advanced routing, `labels/prod` stays on the promoted version until you promote in the UI.

## Update replicas, tier, environment

```python
api = requests.get(f"{base}/api/modelServing/v1/modelApis/{model_api_id}", headers=headers).json()
r = requests.put(f"{base}/api/modelServing/v1/modelApis/{model_api_id}", headers=headers, json={
    "name": api["name"], "description": api["description"],      # required even when unchanged
    "environmentId": api["environmentId"],
    "replicas": 4,
    "hardwareTierId": api.get("hardwareTierId"),
    "resourceQuotaId": api.get("resourceQuotaId"),               # keep the deployment target of remote-data-plane endpoints
})
r.raise_for_status()
```

The PUT is accepted immediately, but the docs say a scale change takes effect only after you restart the endpoint, and the public API has no restart route: restart it from the endpoint page in the UI, then confirm with `GET` (`replicas`, `hardwareTierId`) and the version's deployment status.

## Archive

```python
requests.delete(f"{base}/api/modelServing/v1/modelApis/{model_api_id}", headers=headers).raise_for_status()
api = requests.get(f"{base}/api/modelServing/v1/modelApis/{model_api_id}", headers=headers).json()
assert api["isArchived"]
```

`DELETE` archives; the object stays readable with `isArchived: true`. Stopping a single version has no public route; use **Versions** > **Actions** in the UI.

## Logs

```python
logs = requests.get(
    f"{base}/api/modelServing/v1/modelApis/{model_api_id}/versions/{version_id}/instanceLogs",
    headers=headers, params={"tail": True, "maxResults": 200}).json()["logs"]
build = requests.get(
    f"{base}/api/modelServing/v1/modelApis/{model_api_id}/versions/{version_id}/buildLogs", headers=headers).json()
```

`exportLogs` works the same way. Optional filters: `podName`, `containerName`, `sinceTimeNano` (instance), `buildId`, `sinceTimeNano` (build).

## Registered models by API

```python
# Register the model logged in an MLflow run (POST /api/registeredmodels/v2)
r = requests.post(f"{base}/api/registeredmodels/v2", headers=headers, json={
    "modelName": "churn-gbm",
    "create": True,                                   # create the registered model if it does not exist
    "projectId": os.environ["DOMINO_PROJECT_ID"],
    "description": "GBM churn model",
    "discoverable": False,
    "modelSource": {
        "sourceType": "mlflow",
        "mlflowSource": {"experimentRunId": RUN_ID, "artifactPath": "model"},
    },
})
r.raise_for_status()
version = r.json()["modelVersion"]["modelVersion"]

# Read, patch, versions
requests.get(f"{base}/api/registeredmodels/v1/churn-gbm", headers=headers).json()
requests.patch(f"{base}/api/registeredmodels/v1/churn-gbm", headers=headers, json={"discoverable": True})
requests.get(f"{base}/api/registeredmodels/v1/churn-gbm/versions/{version}", headers=headers).json()
requests.get(f"{base}/api/registeredmodels/v1/churn-gbm/versions/{version}/modelapis", headers=headers).json()
```

`mlflowSource` takes `experimentRunId` (required) plus `artifactPath` or `loggedModelId`; `huggingFaceSource` takes `modelId` (required), `modelRevision`, `huggingFaceToken`. `sourceType` is `mlflow` or `huggingface` and names which of the two you filled in. List with `GET /api/registeredmodels/v2?projectId=...&maxResults=25`; the response's `metadata.nextPageToken` goes into the next request's `pageToken` query parameter until it is absent. `POST /api/registeredmodels/v1/{modelName}/versions` (`description`, `experimentRunId`, `artifact`) still exists but is deprecated since 6.2.1.

## python-domino equivalents

`Domino("owner/project")` (the project argument is required) exposes `models_list()`, `model_publish(file, function, environment_id, name, description, files_to_exclude=None)`, `model_versions_get(model_id)`, `model_version_publish(model_id, file, function, environment_id, description, files_to_exclude=None)` and the export helpers `model_version_export`, `model_version_sagemaker_export`, `model_version_export_status`, `model_version_export_logs`. They call the older `/v1/models` and `/v4` routes (Domino Internal API, may change between Domino versions) and know nothing about replicas, hardware tiers, async endpoints or registry sources; use the public REST routes above for those. See `domino-python-sdk`.
