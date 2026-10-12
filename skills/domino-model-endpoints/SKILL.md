---
name: domino-model-endpoints
description: Publish and call Domino endpoints (model APIs) for synchronous or asynchronous predictions. Covers the prediction function and request JSON, how the endpoint image is built (environment, required packages, no requirements.txt), sync Basic-auth vs async Bearer invocation, versions and routing, instance counts and endpoint hardware tiers, health checks, metrics and logs. Use when deploying a model as an API from the UI, writing predict code, calling an endpoint, or debugging a slow or failing endpoint. For scripted lifecycle automation over REST (create, version, archive, logs) use domino-model-serving; for drift and model-quality monitoring use domino-model-monitoring; for batch scoring Jobs and for exporting a model out of Domino (an image to your registry, NVIDIA Fleet Command, a Snowflake UDF, SageMaker) use domino-model-delivery.
compatibility: Domino 6.3 and Domino Cloud. Management calls need DOMINO_API_HOST; in a run use DOMINO_API_PROXY or the localhost:8899 access-token endpoint, outside a run a Personal Access Token. Prediction calls use the endpoint's own access token.
---

# Domino endpoints (model APIs)

Applies to Domino 6.3 and Domino Cloud.

A Domino endpoint (**Model API** in the API) wraps a function from your project in an HTTP API: Domino builds an image from the selected compute environment plus the project files, adds a Flask (Python) or Plumber (R) harness, sources your script once at publish time, and routes each request to your function.

## Which skill

| Need | Skill |
|------|-------|
| UI publish, predict function, calling, instances, health, logs | this skill |
| REST lifecycle: create, version, list, delete, logs, registered models | `domino-model-serving` |
| Drift, model quality, prediction capture, scheduled checks | `domino-model-monitoring` |
| Score a file, table or Dataset with a Job instead of an endpoint; export the model out of Domino (the endpoint image to your own registry or Kubernetes, NVIDIA Fleet Command, a Snowflake UDF, SageMaker) | [domino-model-delivery](../domino-model-delivery/SKILL.md) |

## Reference files

| File | Use when |
|------|----------|
| [DEPLOY-ENDPOINT.md](./DEPLOY-ENDPOINT.md) | Predict function, sync before publish, health check, calling sync and async, versions, access |
| [SCALING.md](./SCALING.md) | Instance count, endpoint hardware tiers, routing modes, parallelism |
| [MONITORING.md](./MONITORING.md) | CPU, memory, status codes, health checks, timeouts, logs, Grafana |

## Packaging rules (what breaks publishes)

- The environment is chosen per endpoint in the publish form (`environmentId` is required by the API). Python endpoints need `uwsgi`, `flask`, `six` and `prometheus-client` in that environment; async endpoints also need `seldon-core`. Domino Standard Environments ship them (the minimal image lacks `seldon-core` and `mlflow`).
- Endpoint hosts do **not** read `requirements.txt` or run environment setup scripts; put packages in the environment's Dockerfile instructions. Exception: a registry model's MLflow-inferred `requirements.txt` is installed at build.
- Project environment variables are not inherited; set endpoint variables under its **Settings** and restart running versions after changes.
- The image is built from the Project's **committed** files, never the Workspace disk: DFS Project, **File Changes** > **Sync to Domino** first; Git-based, commit and push the code and sync the artifacts. Include every file the function loads (`.py`, model artifacts, lookups) and pin that commit (`version.commitId`): the head lags an upload by seconds, and a missing file crash-loops the container at start with `FileNotFoundError` ("Sync or commit first" in DEPLOY-ENDPOINT.md). Files mount at `/mnt/<username>/<project_name>` (use `DOMINO_WORKING_DIR`); `.modelignore` excludes files; images over 500 MB fail, so exclude large artifacts. New files need a new version.
- The endpoint runs as uid/gid 12574; the image build runs as the Dockerfile's last `USER`.

## Quick start

```python
# model.py (project root)
import pickle
_model = pickle.load(open("model.pkl", "rb"))   # runs once, when the version starts

def predict(sepal_length, sepal_width, petal_length, petal_width):
    pred = _model.predict([[sepal_length, sepal_width, petal_length, petal_width]])
    return {"variety": str(pred[0])}            # JSON-serializable: no NumPy types
```

1. Sync or commit `model.py` and `model.pkl` (packaging rules above), then in the project go to **Deployments** > **Endpoints** > **Create Domino Endpoint**.
2. Enter a name and description, the file (`model.py`) and the function (`predict`).
3. Pick the compute environment, instance count and endpoint hardware tier (SCALING.md).
4. Under **Request Type** choose **Sync** (real-time) or **Async** (long-running; payloads passed by reference).
5. Publish, wait for **Running**, then confirm health: a successful **Tester** request, or the model container's log line `WSGI app 0 (mountpoint='') ready` (a crash-looping container also reports `Running`). The **Overview** tab shows the URL, model ID and code samples.

## Calling an endpoint

Restricted endpoints need an access token from **Settings** > **Invocation**. Sync and async endpoints authenticate differently:

```bash
# Synchronous: HTTP Basic, the token as both username and password
curl -s -u "$MODEL_ACCESS_TOKEN:$MODEL_ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"data": {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}}' \
  "$DOMINO_URL/models/$MODEL_ID/latest/model"

```

Async endpoints take `Authorization: Bearer $MODEL_ACCESS_TOKEN` at `$DOMINO_URL/api/modelApis/async/v1/$MODEL_ID` and return an `asyncPredictionId` to poll (DEPLOY-ENDPOINT.md).

These values come from the user, not from an API. `DOMINO_URL` is the deployment's external URL and `MODEL_ID` its id (Overview tab, "Calling your endpoint"); the token is created and shown only in the UI (**Settings** > **Invocation**). `DOMINO_API_HOST` and `DOMINO_API_PROXY` do not route `/models/...`, no run variable holds the external URL, the API lists token ids but never values, and your own Domino token gets 401 even on a Public endpoint (visibility and authorization are separate). Ask the user for the three values (as project or user environment variables), or for the **Tester** tab, or to set **Unrestricted**, after which only the URL is needed. Never put the token in browser code.

## Versions and routing

Each publish creates a version. **Basic** routing (default) sends `/models/<modelId>/latest/model` to the newest successful version and stops the old one. **Advanced** routing adds a promoted version at `/models/<modelId>/labels/prod/model` so clients stay on production while you test `latest` (**Settings** > **Deployment**). To redeploy on fresh data, schedule a Job and select the endpoint under **Update Domino Endpoint**.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Build fails on an import | The package must be in the environment Dockerfile, not `requirements.txt` |
| `IOException ... HTTP response code: 500` in the build log | Image over 500 MB; add large files to `.modelignore` |
| 401 on predictions | Sync needs Basic auth with the endpoint token; async needs Bearer; a user token or PAT never works |
| `Running` but 503, or `Running` / `Starting` alternating | Crash loop; model-container logs (no `tail`, `maxResults=3000`) show `FileNotFoundError` ... `no app loaded`. Sync, pin the commit, republish |
| 504 on slow requests | Request timeout (default 60 s) under **Settings** > **Advanced**; restart after changing |
| Version not Running | Build, export and instance logs (**Logs** column); health-check settings |

## Documentation

- https://docs.domino.ai/cloud/platform-capabilities/features/model-deployment/index (and its sibling pages)
- Route discovery: [API-SPECS.md](../domino-api-intro/API-SPECS.md)
