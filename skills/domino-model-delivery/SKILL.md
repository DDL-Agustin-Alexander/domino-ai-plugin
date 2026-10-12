---
name: domino-model-delivery
description: Deliver a Domino model outside a Domino endpoint. Covers batch scoring Jobs (a scoring script run once or on a schedule, results, notifications, the async endpoint alternative), the Model Export API used from CI/CD pipelines (buildModelImage, exportImageToRegistry, build and export status and logs, .modelignore, running the exported image on Kubernetes), and the export targets NVIDIA Fleet Command (exportImageForNvidia) and Snowflake (Snowpark UDF), plus where SageMaker fits. Use when the user wants to batch-score a dataset or table with a trained model, run scoring on a schedule, export a model image to a container registry, wire model deployment into GitHub Actions, Jenkins or another CI/CD pipeline, push a model to NVIDIA Fleet Command or Snowflake, or asks about the Exports page. Real-time endpoints are domino-model-endpoints and domino-model-serving.
compatibility: Domino 6.3 and Domino Cloud. Requires DOMINO_API_HOST; in a run use DOMINO_API_PROXY or the localhost:8899 access-token endpoint, outside a run a Personal Access Token. The Model Export routes are Domino Internal API (/v4/models), documented but not in the Public API spec.
---

# Domino model delivery: batch scoring, model export, CI/CD

Applies to Domino 6.3 and Domino Cloud.

Ways to get predictions out of a trained model without serving it as a Domino endpoint.
Endpoints themselves: [domino-model-endpoints](../domino-model-endpoints/SKILL.md) (UI, monitoring)
and [domino-model-serving](../domino-model-serving/SKILL.md) (REST lifecycle).

| Need | Path | Detail |
|---|---|---|
| Score a file, table or Dataset on demand or on a schedule, no latency SLA | **Batch scoring Job**: a Job that runs your scoring script | [BATCH-SCORING.md](./BATCH-SCORING.md) |
| Run the model in your own Kubernetes, staging and CI/CD pipeline | **Model Export API**: Domino builds the endpoint image, pushes it to your registry, you deploy it | [EXPORT-API.md](./EXPORT-API.md) |
| Run the model on NVIDIA edge devices or inside Snowflake | **Export targets**: Fleet Command image plus Helm chart; Snowpark UDF | [EXPORT-TARGETS.md](./EXPORT-TARGETS.md) |
| Serve on Amazon SageMaker | Deployment targets (Public API) or the legacy SageMaker image export | [EXPORT-TARGETS.md](./EXPORT-TARGETS.md#amazon-sagemaker) |

## Authentication

| Where the call runs | Base URL | Credential |
|---|---|---|
| Inside a Domino run, `DOMINO_API_PROXY` set | `$DOMINO_API_PROXY` | none; the proxy adds the starting user's token |
| Inside a run, no proxy | `$DOMINO_API_HOST` | `Authorization: Bearer $(curl -s http://localhost:8899/access-token)` |
| Outside Domino (CI runner, laptop) | the deployment URL users open in a browser | `Authorization: Bearer <Personal Access Token or service-account token>` |

The product pages for export still show `X-Domino-Api-Key`; legacy user API keys are deprecated.
Send a Bearer token instead. Details: https://docs.domino.ai/cloud/reference/api/domino-api-authentication

## Batch scoring in one screen

1. Write a scoring script (for example `score.py`) that loads the model, reads the input (a
   mounted Dataset, a Data Source, or a project file) and writes predictions to a file.
2. Run it as a Job: **Jobs > Run** in the UI, or
   `POST $BASE/api/jobs/v1/jobs` with `{"projectId", "runCommand": "python score.py", "environmentId", "hardwareTier"}`
   (only `projectId` and `runCommand` are required; see [domino-jobs](../domino-jobs/SKILL.md)).
3. Schedule it: **Jobs > Schedules > Schedule a Job**, Quartz cron such as `0 0 2 * * ?`, optional
   **Notify emails** and **Update Domino endpoint**. Scheduled Jobs have no Public API route; the
   product docs say to create them in the UI.
4. Collect results: files the Job added or changed are its results. Poll
   `GET $BASE/api/jobs/beta/jobs/{jobId}` until `status.isCompleted`, then read
   `commitDetails.outputCommitId` and fetch a file with
   `GET $BASE/api/projects/v1/projects/{projectId}/files/{commitId}/{path}/content`.

Too slow? Attach a Spark, Ray or Dask cluster to the Job
([domino-distributed-computing](../domino-distributed-computing/SKILL.md)). Need request/response
semantics for long predictions? Use an **asynchronous endpoint**
(`POST /api/modelApis/async/v1/{asyncModelId}`, Public API); see BATCH-SCORING.md.

## Model Export API in one screen (CI/CD)

The four calls below are **Domino Internal API (`/v4/models/...`), may change between Domino
versions**. They are documented at
https://docs.domino.ai/cloud/platform-capabilities/features/models/integrate-ci-cd-workflows
and in every cluster's own reference under `https://<domino-domain>/docs`, but they are not in
the Public API spec. Labels must stay with every use.

```text
POST /v4/models/buildModelImage                                   -> {modelId, modelVersionId}
GET  /v4/models/{modelId}/{modelVersionId}/getBuildStatus         -> status: Preparing | Building | Complete | Failed
POST /v4/models/{modelId}/{modelVersionId}/exportImageToRegistry  -> {exportId, status}
GET  /v4/models/{exportId}/getExportImageStatus                   -> status (terminal: complete | failed)
GET  /v4/models/{exportId}/getExportLogs                          -> logs
```

Public API complement (both specs): `GET /api/modelServing/v1/modelApis/{modelApiId}/versions/{modelApiVersionId}/exportLogs`.

python-domino wraps export, status and logs (`model_version_export`, `model_version_export_status`,
`model_version_export_logs`) but not the build call. Request bodies, a pipeline script, the
Kubernetes manifests, the test call and `.modelignore`: [EXPORT-API.md](./EXPORT-API.md).

## Export targets in one screen

- **NVIDIA Fleet Command** (beta): `POST /v4/models/{modelId}/{modelVersionId}/exportImageForNvidia`
  with NGC container and Helm repositories, a semver Helm version and an NGC API key; the edge
  port is hardcoded to 30008.
- **Snowflake**: published from the UI as a Snowpark UDF. Python 3.8, a root `requirements.txt`
  limited to the Snowflake Anaconda channel, type-hinted predict function; **Push new version**
  re-exports the project HEAD; drift and quality monitoring from the **Exports** page.
- **SageMaker**: an admin creates a deployment target (`GET/POST /api/admin/v1/deploymentTargets`,
  Public API), then **Endpoints > External > Create external endpoint** or
  `POST /api/modelServing/v1/modelDeployments`. AWS EKS control plane only. The older
  `exportImageForSagemaker` image export (python-domino `model_version_sagemaker_export`) still exists.
- **Exports page** lists every export with target `Sagemaker`, `NvidiaFleetcommand`, `Snowflake`
  or `Domino`; `GET /v4/modelManager/getModelExports/{projectId}` (internal API).

## Pitfalls

- Build first, export second: an export needs a `modelVersionId` whose build reached `Complete`.
- An export fails when the image tag (or Helm chart version) already exists in the target repository.
- Export bodies carry registry, NGC or Snowflake credentials in plain JSON; read them from a secret
  store at run time and never commit them.
- The build body requires `logHttpRequestResponse`; send `false` unless payload logging is wanted.
- Every project file goes into the image unless listed in `.modelignore` at the project root.
- Exported images and Snowflake UDFs cannot reach Domino-only assets (Datasets, Data Sources,
  the API proxy) at inference time; bundle what the model needs.

## Related skills

- [domino-jobs](../domino-jobs/SKILL.md): Job bodies, logs, scheduled Jobs, script patterns
- [domino-model-serving](../domino-model-serving/SKILL.md), [domino-model-endpoints](../domino-model-endpoints/SKILL.md): endpoints
- [domino-model-monitoring](../domino-model-monitoring/SKILL.md): drift and quality for exported models
- [domino-python-sdk](../domino-python-sdk/SKILL.md): python-domino export methods
- [domino-api-intro](../domino-api-intro/SKILL.md): hosts, pagination, errors
