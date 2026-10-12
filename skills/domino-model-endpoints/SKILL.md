---
name: domino-model-endpoints
description: Publish and call Domino endpoints (model APIs) for synchronous or asynchronous predictions. Covers the prediction function and request JSON, how the endpoint image is built (environment, required packages, no requirements.txt), sync Basic-auth vs async Bearer invocation, versions and routing, instance counts and endpoint hardware tiers, health checks, metrics and logs. Use when deploying a model as an API from the UI, writing predict code, calling an endpoint, or debugging a slow or failing endpoint. For scripted lifecycle automation over REST (create, version, archive, logs) use domino-model-serving; for drift and model-quality monitoring use domino-model-monitoring.
compatibility: Domino 6.3 and Domino Cloud. Management calls need DOMINO_API_HOST; in a run use DOMINO_API_PROXY or the localhost:8899 access-token endpoint, outside a run a Personal Access Token. Prediction calls use the endpoint's own access token.
---

# Domino endpoints (model APIs)

Applies to Domino 6.3 and Domino Cloud.

A Domino endpoint wraps a function from your project in an HTTP API. Domino builds an image from the selected compute environment plus the project files, adds a Flask (Python) or Plumber (R) harness, sources your script once at publish time, and routes each request to your function. The UI calls them **Endpoints**; the API calls them **Model APIs**.

## Which skill

| Need | Skill |
|------|-------|
| Publish from the UI, write the predict function, call the endpoint, tune instances, health checks, logs | this skill |
| Automate the lifecycle over REST: create, new version, list, archive, logs, registered models | `domino-model-serving` |
| Drift, model quality, prediction capture, scheduled checks | `domino-model-monitoring` |

## Reference files

| File | Use when |
|------|----------|
| [DEPLOY-ENDPOINT.md](./DEPLOY-ENDPOINT.md) | Prediction function, publish steps, calling sync and async endpoints, versions, access control |
| [SCALING.md](./SCALING.md) | Instance count, endpoint hardware tiers, routing modes, worker parallelism |
| [MONITORING.md](./MONITORING.md) | CPU, memory, status codes, health checks, timeouts, logs, Grafana (admins) |

## Packaging rules (what breaks publishes)

- The environment is chosen per endpoint in the publish form (`environmentId` is required by the API). Python endpoints need `uwsgi`, `flask`, `six` and `prometheus-client` in that environment; async endpoints also need `seldon-core`. Domino Standard Environments ship them (the minimal image lacks `seldon-core` and `mlflow`).
- Endpoint hosts do **not** read `requirements.txt` and do not run the environment's pre/post setup scripts. Put packages in the environment's Dockerfile instructions. One exception: a model registered in the Model Registry gets the `requirements.txt` that MLflow inferred for it, installed at build time.
- Project-level environment variables are not inherited. Set endpoint variables under the endpoint's **Settings** and restart running versions after changing them.
- Project files are baked into the image at build time (new files need a new version) and mounted at `/mnt/<username>/<project_name>`; use `DOMINO_WORKING_DIR` instead of a hardcoded path. Files matched by `.modelignore` in the project root are excluded. Images over 500 MB fail with a storage error, so exclude large artifacts.
- The endpoint runs as uid/gid 12574; the image build runs as the last `USER` in the environment Dockerfile.

## Quick start

```python
# model.py (project root)
import pickle
_model = pickle.load(open("model.pkl", "rb"))   # runs once, when the version starts

def predict(sepal_length, sepal_width, petal_length, petal_width):
    pred = _model.predict([[sepal_length, sepal_width, petal_length, petal_width]])
    return {"variety": str(pred[0])}            # JSON-serializable: no NumPy types
```

1. In the project go to **Deployments** > **Endpoints** > **Create Domino Endpoint**.
2. Enter a name and description, the file (`model.py`) and the function (`predict`).
3. Pick the compute environment, the instance count and the endpoint hardware tier (see SCALING.md).
4. Under **Request Type** choose **Sync** (real-time) or **Async** (long-running; payloads passed by reference).
5. Publish, wait for **Running**, then use the **Tester** tab. The **Overview** tab shows the URL, the model ID and code samples.

## Calling an endpoint

Restricted endpoints need an access token from **Settings** > **Invocation**. Sync and async endpoints authenticate differently:

```bash
# Synchronous: HTTP Basic, the token as both username and password
curl -s -u "$MODEL_ACCESS_TOKEN:$MODEL_ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"data": {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}}' \
  "$DOMINO_URL/models/$MODEL_ID/latest/model"

# Asynchronous: Bearer token; returns asyncPredictionId, then poll
curl -s -H "Authorization: Bearer $MODEL_ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"parameters": {"input_file": "s3://bucket/batch.parquet"}}' \
  "$DOMINO_URL/api/modelApis/async/v1/$MODEL_ID"
```

`DOMINO_URL` and `MODEL_ID` come from "Calling your endpoint" on the Overview tab. Unrestricted endpoints need no token. Request shapes: named parameters take `{"data": {"x": 1}}` or `{"parameters": [1]}`; a function that takes one dict takes `{"parameters": [{"x": 1}]}`. Never embed the token in browser code; call endpoints from a backend.

## Versions and routing

Each publish creates a version. **Basic** routing (default) sends `/models/<modelId>/latest/model` to the newest successful version and shuts the old one down. **Advanced** routing adds a promoted version at `/models/<modelId>/labels/prod/model` so clients stay on production while you test `latest`; switch under **Settings** > **Deployment**. To redeploy on fresh data, schedule a Job and select the endpoint under **Update Domino Endpoint**.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Build fails on an import | Package is in the environment Dockerfile, not only in `requirements.txt` |
| `IOException ... HTTP response code: 500` in the build log | Image over 500 MB; add large files to `.modelignore` |
| 401 on predictions | Sync needs Basic auth with the endpoint token; async needs Bearer |
| `TypeError: ... is not JSON serializable` | Convert NumPy and Decimal values to Python primitives |
| 504 on slow requests | Request timeout (default 60 s) under **Settings** > **Advanced**; restart after changing |
| Version not Running | Build, export and instance logs in the version's **Logs** column; health-check settings |

## Documentation

- https://docs.domino.ai/cloud/platform-capabilities/features/model-deployment/index
- https://docs.domino.ai/cloud/platform-capabilities/features/model-deployment/domino-endpoint-authorization
- https://docs.domino.ai/cloud/platform-capabilities/features/model-deployment/scale
- https://docs.domino.ai/cloud/platform-capabilities/features/model-deployment/monitor-model-endpoints
- Route discovery: [API-SPECS.md](../domino-api-intro/API-SPECS.md)
