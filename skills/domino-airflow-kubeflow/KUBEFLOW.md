# Kubeflow Pipelines and Domino Jobs

Sources: https://docs.domino.ai/cloud/platform-capabilities/features/integrations (Kubeflow tab),
KFP v2 component and `kfp-kubernetes` documentation. Domino ships no Kubeflow-specific package;
the integration is "install `dominodatalab` (or just `requests`) in the component and call the
Domino API", which is what the product page describes.

## Architecture

Kubeflow Pipelines runs in its own Kubernetes cluster, separate from Domino. Each pipeline step
that needs Domino runs as a pod that must reach the Domino deployment URL over the network and
present a Bearer token. The step's code is thin: start a Job, wait, return what the next step
needs. The real work is the Domino Job, versioned in the Domino project.

## Credentials

Create a Kubernetes Secret in the KFP namespace holding a Personal Access Token or a
service-account token (not a legacy API key, which the product page still mentions):

```bash
kubectl -n kubeflow create secret generic domino-token --from-literal=token='<PAT or service-account token>'
```

Expose it to the task as an environment variable with `kfp-kubernetes`:

```bash
pip install "kfp[kubernetes]"
```

```python
from kfp import kubernetes
kubernetes.use_secret_as_env(task, secret_name="domino-token", secret_key_to_env={"token": "DOMINO_TOKEN"})
```

## Component with the Public API

```python
from kfp import dsl, kubernetes

@dsl.component(base_image="python:3.11", packages_to_install=["requests"])
def run_domino_job(domino_url: str, project_id: str, run_command: str,
                   environment_id: str = "", hardware_tier: str = "") -> str:
    """Start a Domino Job, wait for it, return the output commit id."""
    import os, time, requests
    headers = {"Authorization": f"Bearer {os.environ['DOMINO_TOKEN']}"}
    body = {"projectId": project_id, "runCommand": run_command, "title": "kubeflow"}
    if environment_id:
        body["environmentId"] = environment_id
    if hardware_tier:
        body["hardwareTier"] = hardware_tier          # hardware tier id, e.g. small-k8s
    r = requests.post(f"{domino_url}/api/jobs/v1/jobs", headers=headers, json=body, timeout=60)
    r.raise_for_status()
    job_id = r.json()["job"]["id"]
    while True:
        job = requests.get(f"{domino_url}/api/jobs/beta/jobs/{job_id}", headers=headers, timeout=60).json()["job"]
        if job["status"]["isCompleted"]:
            break
        time.sleep(30)
    if job["status"]["executionStatus"] != "Succeeded":
        raise RuntimeError(f"Domino job {job_id} ended {job['status']['executionStatus']}")
    return job["commitDetails"]["outputCommitId"]


@dsl.component(base_image="python:3.11", packages_to_install=["requests"])
def fetch_result(domino_url: str, project_id: str, commit_id: str, path: str, out: dsl.OutputPath(str)):
    """Copy one result file from the Job's output commit into a KFP artifact."""
    import os, urllib.parse, requests
    headers = {"Authorization": f"Bearer {os.environ['DOMINO_TOKEN']}"}
    url = f"{domino_url}/api/projects/v1/projects/{project_id}/files/{commit_id}/{urllib.parse.quote(path, safe='')}/content"
    r = requests.get(url, headers=headers, timeout=300)
    r.raise_for_status()
    with open(out, "wb") as f:
        f.write(r.content)


@dsl.pipeline(name="domino-train-and-collect")
def pipeline(domino_url: str, project_id: str):
    train = run_domino_job(domino_url=domino_url, project_id=project_id, run_command="python train.py")
    kubernetes.use_secret_as_env(train, secret_name="domino-token", secret_key_to_env={"token": "DOMINO_TOKEN"})

    collect = fetch_result(domino_url=domino_url, project_id=project_id,
                           commit_id=train.output, path="results/metrics.json")
    kubernetes.use_secret_as_env(collect, secret_name="domino-token", secret_key_to_env={"token": "DOMINO_TOKEN"})
```

`train.output` is the output commit id; passing it to the next component makes the dependency
explicit and gives the second step a pinned view of the first step's results. The Domino routes
are Public API in both published specs:

```text
POST /api/jobs/v1/jobs
GET  /api/jobs/beta/jobs/{jobId}
GET  /api/jobs/beta/jobs/{jobId}/logs?logType=stdErr
GET  /api/projects/v1/projects/{projectId}/files/{commitId}/{path}/content
```

Chaining Jobs that must run on the previous step's results **inside Domino** (same project):
pass `train.output` as the next Job's `commitId` on a DFS project, or let the next Job read from
the Dataset the first one wrote to.

## Component with python-domino

```python
@dsl.component(base_image="python:3.11", packages_to_install=["dominodatalab"])
def run_with_sdk(domino_url: str, project: str, run_command: str) -> str:
    import os
    from domino import Domino
    d = Domino(project, host=domino_url, auth_token=os.environ["DOMINO_TOKEN"])   # project = "owner/name"
    status = d.job_start_blocking(command=run_command, poll_freq=30, max_poll_time=4 * 3600)
    return status["id"]
```

`job_start_blocking` raises `RunFailedException` on failure and returns the Job object from the
v4 Jobs API (`id`, `statuses.executionStatus`, `commitDetails`, ...; **internal API, may change
between Domino versions**; python-domino owns that dependency). The `Domino(...)` constructor contacts the deployment's `/version` endpoint, so a
pod without network access fails there. Never pass `api_key=`.

## Operational notes

- Set `timeout`s on every request and keep the poll interval at 30 s or more; a pipeline with
  many parallel steps otherwise turns into a steady stream of status calls.
- A KFP retry re-submits the Job; make Jobs idempotent (overwrite the day's partition) or guard
  with a check on the latest completed Job (`GET /api/jobs/beta/jobs?projectId=...&statusFilter=completed`).
- Logs stay in Domino; print the Job id in the component so operators can open it from the KFP
  UI. Pull `stdErr` on failure as the example does.
- `hardwareTier` in the Public body is the tier **id** (the spec example is `small-k8s`), not the
  display name python-domino's `hardware_tier_name` takes.
