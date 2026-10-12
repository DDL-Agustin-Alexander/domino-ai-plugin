# Model Export API: build an endpoint image and push it to your registry

Product page: https://docs.domino.ai/cloud/platform-capabilities/features/models/integrate-ci-cd-workflows
(same content on the 6.3 page). The API turns a project plus an inference function into the same
container image a Domino endpoint runs (environment, project files, Flask or Plumber harness,
auth and load-balancing layer) and pushes it to a registry you own.

**Every `/v4/...` route in this file is Domino Internal API, may change between Domino versions.**
They are not in the Public API spec; each cluster documents them under
`https://<domino-domain>/docs` (`openapi-internal.json`). Field lists below come from that
reference on a Domino Cloud cluster and from the product page.

## Authentication for a pipeline

A CI/CD runner is outside Domino, so use the deployment URL and a Bearer token:

```bash
BASE="https://<deployment URL users open in a browser>"
AUTH="Authorization: Bearer $DOMINO_TOKEN"   # Personal Access Token or service-account token from the CI secret store
```

Inside a Domino run use `$DOMINO_API_PROXY` with no header instead. Do not use
`X-Domino-Api-Key` even though the product page still shows it.

## Sequence

### 1. Build the image

```bash
curl -sS -X POST "$BASE/v4/models/buildModelImage" -H "$AUTH" -H "Content-Type: application/json" -d '{
  "projectId": "<project id>",
  "modelName": "credit-risk",
  "inferenceFunctionFile": "model.py",
  "inferenceFunctionToCall": "predict",
  "environmentId": "<environment id>",
  "logHttpRequestResponse": false,
  "description": "built by pipeline run 123"
}'
```

| Field | Required | Meaning |
|---|---|---|
| `projectId` | yes | project whose files and environment are packaged |
| `modelName` | yes | name of the model in Domino; reuse it to add a version to an existing model |
| `inferenceFunctionFile`, `inferenceFunctionToCall` | yes | file and function Domino calls per request |
| `logHttpRequestResponse` | yes (cluster reference) | log request and response payloads for the model |
| `environmentId` | no | defaults to the project default environment |
| `modelId` | no | build a new version of an existing model instead of a new model |
| `description` | no | free text |

Response: `202 Accepted` with `modelId` and `modelVersionId` (the build continues in the
background). On the cluster reference the response schema is declared as an array wrapping that
object; python-domino's examples read it as an object. Handle both.

### 2. Poll the build

```bash
curl -sS "$BASE/v4/models/$MODEL_ID/$MODEL_VERSION_ID/getBuildStatus" -H "$AUTH"
# {"modelId": "...", "modelVersionId": "...", "status": "Preparing" | "Building" | "Complete" | "Failed"}
curl -sS "$BASE/v4/models/$MODEL_ID/$MODEL_VERSION_ID/getBuildLogs" -H "$AUTH"   # adds "logs"
```

Stop on `Complete` or `Failed`. Compare status values case-insensitively; the product page
capitalises them, python-domino's example tests lowercase `complete` and `failed`.

### 3. Export to your registry

```bash
curl -sS -X POST "$BASE/v4/models/$MODEL_ID/$MODEL_VERSION_ID/exportImageToRegistry" -H "$AUTH" -H "Content-Type: application/json" -d '{
  "registryUrl": "quay.io",
  "repository": "acme/credit-risk",
  "tag": "1.4.0",
  "username": "'"$REGISTRY_USER"'",
  "password": "'"$REGISTRY_PASSWORD"'"
}'
# -> {"modelId", "modelVersionId", "exportId", "status"}
```

`registryUrl` and `repository` are required; `tag`, `username`, `password` are optional on the
cluster reference but a private registry needs the credentials. The export fails when the tag
already exists in the repository, so derive the tag from the version or the pipeline run.

### 4. Poll the export, then read its logs

```bash
curl -sS "$BASE/v4/models/$EXPORT_ID/getExportImageStatus" -H "$AUTH"
# {"modelId", "modelVersionId", "exportId", "status", "errorMessage"?}
curl -sS "$BASE/v4/models/$EXPORT_ID/getExportLogs" -H "$AUTH"
# {"modelId", "modelVersionId", "exportId", "status", "logs"}
```

Public API alternative for the logs, present in both published specs and keyed by the Model API
ids you can list with `GET /api/modelServing/v1/modelApis?projectId=...` and
`GET /api/modelServing/v1/modelApis/{modelApiId}/versions`:

```text
GET /api/modelServing/v1/modelApis/{modelApiId}/versions/{modelApiVersionId}/exportLogs[?sinceTimeNano=...]
-> {"modelId", "modelVersionId", "status", "logs": [{"timestamp", "timeNano", "log", "streamType", "tags"}]}
```

## Pipeline script (bash, any CI system)

```bash
#!/usr/bin/env bash
# Needs: BASE, DOMINO_TOKEN, PROJECT_ID, ENVIRONMENT_ID, REGISTRY_USER, REGISTRY_PASSWORD, TAG
set -euo pipefail
AUTH="Authorization: Bearer $DOMINO_TOKEN"
# field <key>: print one key from a JSON object (or from the first element if the server wraps it in an array)
field() { python3 -c 'import json,sys; d=json.load(sys.stdin); d=d[0] if isinstance(d,list) else d; print(d[sys.argv[1]])' "$1"; }
lower() { tr "[:upper:]" "[:lower:]"; }

build=$(curl -sSf -X POST "$BASE/v4/models/buildModelImage" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"projectId\":\"$PROJECT_ID\",\"modelName\":\"credit-risk\",\"inferenceFunctionFile\":\"model.py\",\"inferenceFunctionToCall\":\"predict\",\"environmentId\":\"$ENVIRONMENT_ID\",\"logHttpRequestResponse\":false}")
model_id=$(echo "$build" | field modelId); version_id=$(echo "$build" | field modelVersionId)

until status=$(curl -sSf "$BASE/v4/models/$model_id/$version_id/getBuildStatus" -H "$AUTH" | field status | lower); \
      [ "$status" = complete ] || [ "$status" = failed ]; do sleep 20; done
[ "$status" = complete ] || { curl -sS "$BASE/v4/models/$model_id/$version_id/getBuildLogs" -H "$AUTH"; exit 1; }

export_id=$(curl -sSf -X POST "$BASE/v4/models/$model_id/$version_id/exportImageToRegistry" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"registryUrl\":\"quay.io\",\"repository\":\"acme/credit-risk\",\"tag\":\"$TAG\",\"username\":\"$REGISTRY_USER\",\"password\":\"$REGISTRY_PASSWORD\"}" | field exportId)

until status=$(curl -sSf "$BASE/v4/models/$export_id/getExportImageStatus" -H "$AUTH" | field status | lower); \
      [ "$status" = complete ] || [ "$status" = failed ]; do sleep 20; done
curl -sS "$BASE/v4/models/$export_id/getExportLogs" -H "$AUTH"
[ "$status" = complete ]
echo "quay.io/acme/credit-risk:$TAG"
```

Store `DOMINO_TOKEN` and the registry credentials as CI secrets (GitHub Actions `secrets.*`,
Jenkins credentials). The same calls from a GitHub Actions workflow for a Domino **App** are in
[domino-apps REACT-CICD.md](../domino-apps/REACT-CICD.md).

## python-domino equivalents

`python-domino` (`pip install dominodatalab`) wraps the export calls; there is no wrapper for
`buildModelImage`. Methods, verified in `domino/domino.py` on `master`:

| Method | Calls |
|---|---|
| `models_list()` | `GET /v4/models` for the client's project |
| `model_versions_get(model_id)` | versions of a model; each has `_id` and `metadata.number` |
| `model_version_export(model_id, model_version_id, registry_host, registry_username, registry_password, repository_name, image_tag)` | `exportImageToRegistry` |
| `model_version_sagemaker_export(...)` (same arguments) | `exportImageForSagemaker` |
| `model_version_export_status(model_export_id)` | `getExportImageStatus` |
| `model_version_export_logs(model_export_id)` | `getExportLogs` |

```python
import os, time
from domino import Domino

d = Domino("owner/project", host=os.environ["DOMINO_API_HOST"], auth_token=os.environ["DOMINO_TOKEN"])  # PAT outside a run
export = d.model_version_export(model_id, model_version_id, "quay.io", os.environ["REGISTRY_USER"],
                                os.environ["REGISTRY_PASSWORD"], "acme/credit-risk", "1.4.0")
while export.get("status", "").lower() not in ("complete", "failed"):
    time.sleep(10)
    export = d.model_version_export_status(export["exportId"])
print(d.model_version_export_logs(export["exportId"]))
```

Inside a run leave `host` and `auth_token` out: the client picks up `DOMINO_API_PROXY`.
Never pass `api_key=`.

## Run the exported image in staging

The image listens on **8888** and serves predictions at `/model`. Sample manifests from the
product page (image, names and ports are yours to change):

```yaml
# my-model-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata: {name: mymodel, labels: {app: mymodel}}
spec:
  replicas: 1
  selector: {matchLabels: {app: mymodel}}
  template:
    metadata: {labels: {app: mymodel}}
    spec:
      containers:
        - name: mymodel
          image: quay.io/acme/credit-risk:1.4.0
          ports: [{name: mymodel, containerPort: 8888}]
---
# my-model-service.yaml
apiVersion: v1
kind: Service
metadata: {name: mymodel-service}
spec:
  type: NodePort
  selector: {app: mymodel}
  ports: [{nodePort: 31440, name: mymodel-port, port: 90, targetPort: 8888}]
```

```bash
kubectl apply -f my-model-deployment.yaml -f my-model-service.yaml   # add an imagePullSecret for a private registry
PORT=$(kubectl get service/mymodel-service -o jsonpath='{.spec.ports[?(@.name=="mymodel-port")].nodePort}')
curl -sS -X POST "http://<node ip>:$PORT/model" -H "Content-Type: application/json" -d '{"data": {"start": 1, "stop": 100}}'
```

The `data` object is passed to your inference function as its arguments, exactly as a Domino
endpoint would. Promote the same image to production once staging tests pass.

## `.modelignore`

By default every project file is copied into the image. Put file names, folder names or UNIX
shell patterns in `.modelignore` at the project root to leave them out (training data, notebooks,
large artifacts the model does not load).
