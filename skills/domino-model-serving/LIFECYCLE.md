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

`GET /api/modelServing/v1/modelApis/{modelApiId}` returns the same object: `id`, `name`, `description`, `environmentId`, `hardwareTierId`, `replicas`, `routingMode` (`Basic` or advanced), `isAsync`, `strictNodeAntiAffinity`, `access{isPublic, accessTokens[]}`, `healthCheck{...}`, `overrideRequestTimeoutSecs`, `collaborators[]`, `volumes[]`, `activeVersion{id, number, dataPlaneId, deployment{status, isPending}}`, `metadata{created, createdBy, lastModified}`.

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
```

## Create from a registered model

Same body with `"source": {"type": "Registry", "registeredModelName": "churn-gbm", "registeredModelVersion": 3}`. The `requirements.txt` MLflow inferred when the model was logged is installed into the image.

## Wait until Running

```python
def wait_running(model_api_id, timeout_s=1800):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        api = requests.get(f"{base}/api/modelServing/v1/modelApis/{model_api_id}", headers=headers).json()
        deployment = api.get("activeVersion", {}).get("deployment")      # absent until a deployment exists
        status = deployment["status"] if deployment else "Pending"
        if status == "Running" and not deployment["isPending"]:
            return api
        if status in ("Failed", "Stopped"):
            raise RuntimeError(f"endpoint {model_api_id} is {status}")
        time.sleep(15)
    raise TimeoutError(model_api_id)
```

`Running` is the documented ready state. Other values are strings the service reports; treat anything that is not `Running` and not pending as a reason to read the build and instance logs (below).

## Prediction URL

```python
deployment_url = os.environ["DOMINO_URL"]          # the deployment URL, as shown on the endpoint Overview tab
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
    "description": "retrained 2026-10",
})
r.raise_for_status()
version_id = r.json()["id"]
wait_running(model_api_id)
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
})
r.raise_for_status()
```

A scale change restarts the endpoint.

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

`mlflowSource` takes `experimentRunId` (required) plus `artifactPath` or `loggedModelId`; `huggingFaceSource` takes `modelId` (required), `modelRevision`, `huggingFaceToken`. `sourceType` is `mlflow` or `huggingface` and names which of the two you filled in. List with `GET /api/registeredmodels/v2?projectId=...&maxResults=25` and follow `metadata.pageToken`. `POST /api/registeredmodels/v1/{modelName}/versions` (`description`, `experimentRunId`, `artifact`) still exists but is deprecated since 6.2.1.

## python-domino equivalents

`Domino("owner/project")` (the project argument is required) exposes `models_list()`, `model_publish(file, function, environment_id, name, description, files_to_exclude=None)`, `model_versions_get(model_id)`, `model_version_publish(model_id, file, function, environment_id, description, files_to_exclude=None)` and the export helpers `model_version_export`, `model_version_sagemaker_export`, `model_version_export_status`, `model_version_export_logs`. They call the older `/v1/models` and `/v4` routes (Domino Internal API, may change between Domino versions) and know nothing about replicas, hardware tiers, async endpoints or registry sources; use the public REST routes above for those. See `domino-python-sdk`.
