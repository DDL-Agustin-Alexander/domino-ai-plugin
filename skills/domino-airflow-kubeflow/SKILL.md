---
name: domino-airflow-kubeflow
description: Run Domino Jobs from an external orchestrator. Covers Apache Airflow (python-domino's DominoOperator and DominoSparkOperator, or a PythonOperator that calls the Jobs API), Kubeflow Pipelines (a KFP component that starts a Job over REST or python-domino and polls it), installing python-domino on workers, credentials outside Domino (Personal Access Token or service-account token, never an API key), network reachability, mapping DAG tasks to Jobs, polling status, fetching logs and results. Use when the user mentions Airflow, a DAG, DominoOperator, Kubeflow, KFP, an external scheduler or orchestrator, or wants a pipeline that lives outside Domino to trigger and wait for Domino Jobs. For pipelines inside Domino use domino-flows; for a recurring single Job use a scheduled Job (domino-jobs).
compatibility: Domino 6.3 and Domino Cloud. The orchestrator runs outside Domino, so it needs the deployment URL and a Personal Access Token or service-account token; DOMINO_API_PROXY and the localhost:8899 access-token endpoint exist only inside Domino runs. python-domino 2.x (the Airflow operators ship with it).
---

# Airflow and Kubeflow integration

Applies to Domino 6.3 and Domino Cloud.

Product page: https://docs.domino.ai/cloud/platform-capabilities/features/integrations (6.3:
same path under `/6.3/`). The orchestrator is its own service outside Domino; each pipeline step
starts a Domino **Job** through the Domino API and waits for it; the code that does the work
lives in the Domino project. Domino keeps reproducibility, the orchestrator keeps the schedule.

## Pick the right tool first

| Situation | Use |
|---|---|
| Multi-step DAG that should run **inside** Domino with lineage and typed artifacts | [domino-flows](../domino-flows/SKILL.md) |
| One Job on a cron | a scheduled Job, [domino-jobs](../domino-jobs/SKILL.md) |
| An existing Airflow or Kubeflow deployment already orchestrates the data estate | this skill |

## What the orchestrator needs

1. **Network path** from its workers to the Domino deployment URL (the one users open in a
   browser). Nothing from inside a run (`DOMINO_API_PROXY`, `localhost:8899`,
   `http://127.0.0.1:8763`) exists on an Airflow worker or a KFP pod.
2. **A token**: a Personal Access Token for a pipeline that acts as you, or a service-account
   token for unattended automation, kept in the orchestrator's secret store. Legacy user API
   keys are deprecated; the product page and python-domino's example still show
   `DOMINO_API_KEY` / `DOMINO_USER_API_KEY`, do not copy that.
   https://docs.domino.ai/cloud/reference/api/domino-api-authentication
3. **Project id and command** per step, plus optional environment id and hardware tier id.

## Airflow in one screen

```bash
pip install dominodatalab     # on every Airflow worker; the [airflow] extra pins apache-airflow==2.2.4, so skip it on an existing Airflow
```

```python
from airflow import DAG
from airflow.models import Variable
from domino.airflow import DominoOperator

with DAG("domino_pipeline", schedule="@daily", catchup=False) as dag:
    train = DominoOperator(
        task_id="train",
        project="acme/churn",
        host=Variable.get("DOMINO_API_HOST"),            # deployment URL
        domino_token_file="/var/run/secrets/domino/token",  # file whose first line is the PAT or SA token
        command=["train.py", "--epochs", "20"],          # list: file first, then arguments
        tier="Medium",                                   # hardware tier NAME, validated before start
        max_poll_time=2 * 60 * 60,
    )
```

`DominoOperator` starts the Job through python-domino's `runs_start_blocking` (legacy v1 Runs
API), polls until it finishes, replays the Job log into the task log and fails the task if the
Job did not succeed. `DominoSparkOperator` does the same through `job_start_blocking` (v4 Jobs
API, internal) and adds `environment_id`, `hardware_tier_name` and `compute_cluster_properties`
for a Spark, Ray, Dask or MPI cluster. Neither accepts `auth_token`, so a token goes in through
`domino_token_file` (or the `DOMINO_TOKEN_FILE` environment variable on the worker). Parameter
tables, a PythonOperator alternative on the Public API, XCom: [AIRFLOW.md](./AIRFLOW.md).

## Kubeflow in one screen

No Domino-specific KFP component exists; the product page says to install `dominodatalab` on the
cluster and call the API. A lightweight component that starts a Job and waits:

```python
from kfp import dsl, kubernetes

@dsl.component(base_image="python:3.11", packages_to_install=["requests"])
def run_domino_job(domino_url: str, project_id: str, run_command: str) -> str:
    import os, time, requests
    h = {"Authorization": f"Bearer {os.environ['DOMINO_TOKEN']}"}
    job = requests.post(f"{domino_url}/api/jobs/v1/jobs", headers=h,
                        json={"projectId": project_id, "runCommand": run_command}).json()["job"]
    while True:
        job = requests.get(f"{domino_url}/api/jobs/beta/jobs/{job['id']}", headers=h).json()["job"]
        if job["status"]["isCompleted"]:
            break
        time.sleep(30)
    if job["status"]["executionStatus"] != "Succeeded":
        raise RuntimeError(f"Domino job {job['id']} ended {job['status']['executionStatus']}")
    return job["commitDetails"]["outputCommitId"]

@dsl.pipeline(name="domino-train")
def pipeline(domino_url: str, project_id: str):
    t = run_domino_job(domino_url=domino_url, project_id=project_id, run_command="python train.py")
    kubernetes.use_secret_as_env(t, secret_name="domino-token", secret_key_to_env={"token": "DOMINO_TOKEN"})
```

`pip install kfp[kubernetes]` supplies `kfp.kubernetes`. Chaining steps, passing the output
commit on, and a python-domino variant: [KUBEFLOW.md](./KUBEFLOW.md).

## The Jobs API calls both integrations rely on

Public API, in both published specs:

```text
POST /api/jobs/v1/jobs                      {projectId, runCommand, title?, environmentId?, hardwareTier?, commitId?, mainRepoGitRef?, computeCluster?}
GET  /api/jobs/beta/jobs/{jobId}            -> job.status.{isCompleted, executionStatus}, job.commitDetails.outputCommitId
GET  /api/jobs/beta/jobs/{jobId}/logs       ?logType=stdOut|stdErr|prepareOutput|complete
GET  /api/projects/v1/projects/{projectId}/files/{commitId}/{path}/content   (read a result file)
```

Full polling helper, result hand-off between steps and failure handling:
[JOBS-API-PATTERN.md](./JOBS-API-PATTERN.md).

## Pitfalls

- `DominoOperator.command` is a **list**; with `isDirect=True` pass the whole shell command as
  its single element (`command=["python -V"]`).
- `tier` on `DominoOperator` is validated against hardware tier **names** visible to the project;
  a wrong name raises before anything starts.
- Constructing `Domino(...)` calls the deployment's `/version` endpoint, so a worker with no
  network path to Domino fails at client creation, not at Job start.
- Default `max_poll_time` is 6000 s (100 min); longer Jobs need a larger value or the task fails
  while the Job keeps running.
- python-domino reads `DOMINO_API_HOST` (host) and `DOMINO_TOKEN_FILE` from the environment; the
  product page's `DOMINO_API_KEY` is an Airflow Variable name, not something the SDK reads.
- The operators import `airflow.utils.decorators.apply_defaults`, a deprecated no-op in Airflow 2
  that Airflow 3.0 removed. On Airflow 3 use the PythonOperator pattern in AIRFLOW.md.
- Each step is a separate Job with its own input commit; hand data between steps through
  Datasets, Data Sources or the output commit, not the local filesystem.

## Related skills

- [domino-jobs](../domino-jobs/SKILL.md): Job bodies, hardware tiers, logs, scheduled Jobs
- [domino-flows](../domino-flows/SKILL.md): orchestration inside Domino
- [domino-python-sdk](../domino-python-sdk/SKILL.md): python-domino client and auth order
- [domino-api-intro](../domino-api-intro/SKILL.md): hosts, pagination, errors
