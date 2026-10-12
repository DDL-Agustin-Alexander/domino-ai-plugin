# Domino Models API

Model APIs (hosted prediction endpoints), Model Deployments, the Registered Models
registry, and how to invoke an endpoint. Routes and fields are from both published specs
unless marked **Cloud**. Lifecycle guidance and the v1/v2 registry split:
[API-MODEL-SERVING.md](./API-MODEL-SERVING.md) and
[domino-model-serving](../domino-model-serving/SKILL.md); deployment workflow and
monitoring: [domino-model-endpoints](../domino-model-endpoints/SKILL.md).

## Authentication

Use the shared setup block (`base_url`, `headers`) from
[domino-api-intro](../domino-api-intro/SKILL.md#authentication). Invoking an endpoint
uses that endpoint's own access token instead (below).

## Model APIs

### List

```
GET /api/modelServing/v1/modelApis
```

Filters: `projectId`, `environmentId`, `name`, `registeredModelName`,
`registeredModelVersion`, `limit`, `offset`, `orderBy`. Response: `{"items": [...]}`.
Each item has `id`, `name`, `description`, `isArchived`, `environmentId`,
`hardwareTierId`, `replicas`, `isAsync`, `routingMode`, `access` (`isPublic`,
`accessTokens[]`), `activeVersion` (`id`, `number`, `dataPlaneId`, `deployment.status`),
`collaborators`, `metadata`.

```python
items = requests.get(f"{base_url}/api/modelServing/v1/modelApis", headers=headers,
                     params={"projectId": project_id}).json()["items"]
```

### Create

```
POST /api/modelServing/v1/modelApis
```

Required: `name`, `description`, `environmentId`, `isAsync`, `strictNodeAntiAffinity`,
`environmentVariables` (array, may be empty), `version`. Optional: `hardwareTierId`,
`replicas`, `resourceQuotaId`, `bundleId` (governance).

`version` (required fields `projectId`, `source`, `logHttpRequestResponse`,
`monitoringEnabled`): `source.type` is `File` (`file`, `function`, optional
`excludeFiles`) or `Registry` (`registeredModelName`, `registeredModelVersion`); optional
`commitId`, `environmentId`, `shouldDeploy`, `recordInvocation`,
`predictionDatasetResourceId`, `provenanceCheckpointId`.

```python
model_api = requests.post(f"{base_url}/api/modelServing/v1/modelApis", headers=headers, json={
    "name": "customer-churn",
    "description": "Predicts customer churn probability",
    "environmentId": env_id,
    "hardwareTierId": "small-k8s",
    "isAsync": False,
    "strictNodeAntiAffinity": False,
    "environmentVariables": [],
    "version": {
        "projectId": project_id,
        "source": {"type": "File", "file": "serve.py", "function": "predict"},
        "logHttpRequestResponse": False,
        "monitoringEnabled": False,
        "shouldDeploy": True,
    },
}).json()
model_api_id = model_api["id"]
```

### Get, update, delete

```
GET    /api/modelServing/v1/modelApis/{modelApiId}
PUT    /api/modelServing/v1/modelApis/{modelApiId}
DELETE /api/modelServing/v1/modelApis/{modelApiId}
```

The GET response carries `access.accessTokens[]` (token ids and metadata, not the secret
values) and `activeVersion.deployment.status`. It does not include the invocation URL;
read that from the Model API's page in Domino.

**Cloud only:** `PUT /api/modelServing/beta/modelApis/{modelApiId}/access`,
`GET/PUT .../visibility`, `GET/POST .../collaborators`, `GET .../consumer/access`.

### Versions and logs

```
GET  /api/modelServing/v1/modelApis/{modelApiId}/versions
POST /api/modelServing/v1/modelApis/{modelApiId}/versions
GET  /api/modelServing/v1/modelApis/{modelApiId}/versions/{modelApiVersionId}
GET  /api/modelServing/v1/modelApis/{modelApiId}/versions/{modelApiVersionId}/buildLogs
GET  /api/modelServing/v1/modelApis/{modelApiId}/versions/{modelApiVersionId}/exportLogs
GET  /api/modelServing/v1/modelApis/{modelApiId}/versions/{modelApiVersionId}/instanceLogs
```

New-version body is the `version` object above (`projectId`, `source`,
`logHttpRequestResponse`, `monitoringEnabled` required).

## Model Deployments

```
GET, POST          /api/modelServing/v1/modelDeployments
GET, PATCH, DELETE /api/modelServing/v1/modelDeployments/{modelDeploymentId}
POST               /api/modelServing/v1/modelDeployments/{modelDeploymentId}/start | /stop
GET                /api/modelServing/v1/modelDeployments/{modelDeploymentId}/versions[/{version}]
GET                /api/modelServing/v1/modelDeployments/{modelDeploymentId}/logs/{logSuffix}
GET                /api/modelServing/v1/modelDeployments/{modelDeploymentId}/credentials[/{operationType}]
```

The create body is large: `models[]` (each with `name`, `source` naming a registered
model and version, optional `environmentId`), `configuration` (`deploymentType.type`
`SYNC_ENDPOINT` or `ASYNC_ENDPOINT`, `sharedConfig`, `modelConfigs`), `deploymentTargetId`,
`collaborators[]` (`id`, `role` `OWNER`/`CONSUMER`), `isGloballyAccessible`. Pull the
schema from the spec ([API-SPECS.md](../domino-api-intro/API-SPECS.md)) before composing
it; deployment targets come from `GET /api/admin/v1/deploymentTargets/selectable`.

## Registered models (registry)

List and register use v2; get, update, versions use v1 keyed by **model name**.

```
GET  /api/registeredmodels/v2            params: projectId, searchPattern, modelCategory (genai|ml), pageToken, maxResults, orderBy
POST /api/registeredmodels/v2
GET  /api/registeredmodels/v1/{modelName}
PATCH /api/registeredmodels/v1/{modelName}
GET  /api/registeredmodels/v1/{modelName}/versions
POST /api/registeredmodels/v1/{modelName}/versions     body: {"experimentRunId": "...", "artifact": "...", "description": "..."} (all required)
GET  /api/registeredmodels/v1/{modelName}/versions/{version}
GET  /api/registeredmodels/v1/{modelName}/versions/{version}/modelapis
GET  /api/registeredmodels/v2/{modelName}/versions[/{version}]
```

Register (`POST /api/registeredmodels/v2`) requires `modelName`, `modelSource` and
`create` (boolean: create the registered model if it does not exist). `modelSource` is
`{"sourceType": "mlflow", "mlflowSource": {"experimentRunId": "...", "artifactPath": "models/my_model"}}`
or `{"sourceType": "huggingface", "huggingFaceSource": {"modelId": "org/model"}}`.
Optional: `projectId`, `modelCategory`, `modelType`, `discoverable`.

```python
requests.post(f"{base_url}/api/registeredmodels/v2", headers=headers, json={
    "modelName": "fraud-classifier",
    "create": True,
    "projectId": project_id,
    "modelSource": {"sourceType": "mlflow",
                    "mlflowSource": {"experimentRunId": run_id, "artifactPath": "model"}},
})
```

Registry list responses use `{"items": [...]}` with `pageToken` pagination; items carry
`name`, `latestVersion`, `project`, `tags`.

## Invoking a Model API

Use the invocation URL shown on the Model API's page (not `$DOMINO_API_HOST`), with
the endpoint's access token. Per
https://docs.domino.ai/cloud/platform-capabilities/features/model-deployment/domino-endpoint-authorization:

- Restricted **synchronous** endpoint: HTTP Basic, username and password both the token.
- Restricted **asynchronous** endpoint: `Authorization: Bearer <token>`.
- Unrestricted endpoint: no credentials.

```python
# Synchronous (URL copied from the Model API page in Domino)
response = requests.post(
    model_api_url,
    auth=(model_access_token, model_access_token),
    json={"data": {"features": [1.0, 2.0, 3.0, 4.0]}},
)
prediction = response.json()
```

Asynchronous endpoints use the Public API routes:

```python
submitted = requests.post(f"{base_url}/api/modelApis/async/v1/{model_api_id}",
                          headers={"Authorization": f"Bearer {model_access_token}"},
                          json={"parameters": {"input_file": "s3://bucket/data.csv"}}).json()
prediction_id = submitted["asyncPredictionId"]

import time
while True:
    result = requests.get(f"{base_url}/api/modelApis/async/v1/{model_api_id}/{prediction_id}",
                          headers={"Authorization": f"Bearer {model_access_token}"}).json()
    if result.get("result") is not None or result.get("errors"):
        break
    print("status:", result["status"])
    time.sleep(5)
print(result.get("result"), result.get("errors"))
```

`parameters` is required on submit; the poll response has `asyncPredictionId`, `status`
(a string the spec does not enumerate), optional `result` and `errors[]`. Stop when
`result` or `errors` is populated.

## python-domino

`models_list()`, `model_publish(file, function, environment_id, name, description, files_to_exclude=None)`,
`model_versions_get(model_id)`, `model_version_publish(model_id, file, function, environment_id, description, files_to_exclude=None)`
and the `model_version_export*` methods call the legacy `/v1/models` and `/v4/models`
routes. Signatures and a publish example: [SDK-EXAMPLES.md](./SDK-EXAMPLES.md#model-apis-and-apps).
There is no `model_get` or `runs_wait`.
