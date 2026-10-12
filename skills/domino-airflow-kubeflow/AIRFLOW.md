# Apache Airflow and Domino Jobs

Sources: https://docs.domino.ai/cloud/platform-capabilities/features/integrations (Airflow tab),
python-domino `domino/airflow/_operator.py`, `domino/authentication.py` and `examples/example_airflow_dag.py`
on `master` (https://github.com/dominodatalab/python-domino). Everything below was checked
against that source; parameter names are exact.

## Install on the workers

```bash
pip install dominodatalab            # on a worker that already runs Airflow
```

`domino.airflow` only needs `airflow` importable, which an Airflow worker already has. The
`dominodatalab[airflow]` extra that python-domino's README advertises pins `apache-airflow==2.2.4`
(`setup.py` on `master`), so on a modern Airflow it would try to replace your Airflow; use the
extra only in a fresh virtual environment where that version is acceptable. Tasks that call
Domino need `LocalExecutor` or another executor that runs them on workers with network access to
the Domino deployment URL.

## Credentials on a worker

python-domino's auth precedence (`domino/authentication.py`): `api_proxy` > `auth_token` >
`domino_token_file` > `api_key` > env `DOMINO_API_PROXY` > env `DOMINO_TOKEN_FILE` > env
`DOMINO_USER_API_KEY`. The host comes from the `host` argument or env `DOMINO_API_HOST`.

The two operators expose `host`, `api_key` and `domino_token_file` only. To stay off API keys:

| Option | How |
|---|---|
| Token file (operator argument) | Write the PAT or service-account token as the first line of a file the worker can read (a mounted Kubernetes Secret, a file deployed by your secrets manager) and pass `domino_token_file="/path/to/token"`. The client re-reads the file on every request, so rotating the token in place needs no restart. |
| Token file (environment) | Set `DOMINO_TOKEN_FILE=/path/to/token` and `DOMINO_API_HOST=https://<deployment>` in the worker environment and omit `host` and `domino_token_file`. |
| Token string | Only possible with your own `PythonOperator` (below): `Domino(project, host=..., auth_token=...)`. |

Airflow Variables are fine for the host; keep the token out of Variables unless the Variable is
backed by a secrets backend.

## `DominoOperator`

```python
from domino.airflow import DominoOperator
```

| Parameter | Type / default | Meaning |
|---|---|---|
| `project` | `str`, required | `owner/project-name` |
| `command` | `List[str]`, required | file to run first, then arguments; templated |
| `host` | `str`, `None` | deployment URL; else env `DOMINO_API_HOST` |
| `api_key` | `str`, `None` | legacy API key; do not use |
| `domino_token_file` | `str`, `None` | path to a file holding a Bearer token |
| `isDirect` | `bool`, `None` | run `command[0]` as a shell command; must then be a single element |
| `commitId` | `str`, `None` | DFS commit to run from (not a git SHA on a Git-based project) |
| `title` | `str`, `None` | Job title; templated |
| `tier` | `str`, `None` | hardware tier **name**; checked against `hardware_tiers_list()` before start |
| `publishApiEndpoint` | `bool`, `None` | republish the project's endpoint after the Job |
| `poll_freq` | `int`, `5` | seconds between status polls |
| `max_poll_time` | `int`, `6000` | seconds before the task fails (the Job keeps running) |
| `startup_delay` | `int`, `10` | seconds to sleep before starting |
| `include_setup_log` | `bool`, `True` | prefix the replayed log with the Job's setup log |

Behaviour (`execute`): builds `Domino(project, api_key, host, domino_token_file)`, validates
`tier`, sleeps `startup_delay`, calls `runs_start_blocking(...)` (legacy v1 Runs API: `command`,
`isDirect`, `commitId`, `title`, `tier`, `publishApiEndpoint`), then `get_run_log(run_id,
include_setup_log)` and `process_log(log)` into the task log. Returns the start response (a dict
with `runId`), which Airflow stores as the task's XCom return value. A Job that ends in any
state other than `Succeeded` raises `RunFailedException`; exceeding `max_poll_time` raises too.

## `DominoSparkOperator`

```python
from domino.airflow import DominoSparkOperator
```

Same `project`, `host`, `api_key`, `domino_token_file`, `poll_freq`, `max_poll_time`,
`startup_delay`, plus:

| Parameter | Type / default | Meaning |
|---|---|---|
| `command` | `str`, required | one string, for example `"main.py arg1 arg2"`; templated |
| `commit_id` | `str`, `None` | as above |
| `hardware_tier_name` | `str`, `None` | hardware tier name (python-domino resolves it to an id) |
| `environment_id` | `str`, `None` | environment id; default is the project's |
| `compute_cluster_properties` | `dict`, `None` | `{"clusterType": "Spark" \| "Ray" \| "Dask" \| "MPI", "computeEnvironmentId", "computeEnvironmentRevisionSpec"?, "masterHardwareTierId" (not for MPI), "workerCount", "workerHardwareTierId", "workerStorage"?: {"value", "unit": "GiB" \| "MB"}, "maxWorkerCount"?}` |
| `on_demand_spark_cluster_properties` | `dict`, `None` | deprecated; ignored when `compute_cluster_properties` is set |

Behaviour: `job_start_blocking(command=..., commit_id=..., hardware_tier_name=..., environment_id=...,
poll_freq=..., max_poll_time=..., on_demand_spark_cluster_properties=..., compute_cluster_properties=...)`
over the v4 Jobs API (**internal API, may change between Domino versions**; python-domino owns
that dependency). Returns the final job status dict (`statuses.executionStatus`,
`statuses.isCompleted`); raises `RunFailedException` on `Failed`.

Despite the name it is the operator to use for **any** Job that needs an explicit environment or
a compute cluster, Spark or not.

## DAG example

```python
from datetime import datetime
from airflow import DAG
from airflow.models import Variable
from domino.airflow import DominoOperator, DominoSparkOperator

HOST = Variable.get("DOMINO_API_HOST")           # https://<deployment>
TOKEN_FILE = "/var/run/secrets/domino/token"     # mounted secret, first line = PAT or SA token

with DAG("churn_pipeline", start_date=datetime(2026, 1, 1), schedule="0 2 * * *", catchup=False) as dag:
    prepare = DominoOperator(
        task_id="prepare_data",
        project="acme/churn",
        host=HOST, domino_token_file=TOKEN_FILE,
        command=["prepare.py", "--as-of", "{{ ds }}"],
        tier="Small",
        max_poll_time=3600,
    )
    train = DominoSparkOperator(
        task_id="train_on_spark",
        project="acme/churn",
        host=HOST, domino_token_file=TOKEN_FILE,
        command="train.py --as-of {{ ds }}",
        environment_id="<spark-enabled environment id>",
        hardware_tier_name="Medium",
        compute_cluster_properties={
            "clusterType": "Spark",
            "computeEnvironmentId": "<spark cluster environment id>",
            "masterHardwareTierId": "<tier id>",
            "workerHardwareTierId": "<tier id>",
            "workerCount": 4,
        },
        max_poll_time=4 * 3600,
    )
    prepare >> train
```

`{{ ds }}` works because `command` and `title` are template fields. `prepare` finishes before
`train` starts; the data hand-off happens through the Domino project (results committed by the
first Job are the input commit of the second) or through a Dataset.

## PythonOperator with the Public API (no operator import)

python-domino 2.2.0's operators import `airflow.utils.decorators.apply_defaults`, which Airflow 2
keeps as a deprecated no-op and which is absent from Airflow 3.0's `airflow/utils/decorators.py`,
so on Airflow 3 `from domino.airflow import DominoOperator` raises `ImportError`. Use this
pattern there, and whenever you want the Public `/api/jobs/v1/jobs` route with `environmentId`,
`hardwareTier` (tier **id**), `mainRepoGitRef` or `netAppVolumeIds`, or the output commit id as
an XCom value.

```python
from airflow.decorators import task

@task
def run_domino_job(run_command: str, project_id: str) -> str:
    import os, time, requests
    base = os.environ["DOMINO_API_HOST"].rstrip("/")
    headers = {"Authorization": "Bearer " + open(os.environ["DOMINO_TOKEN_FILE"]).readline().strip()}
    job = requests.post(f"{base}/api/jobs/v1/jobs", headers=headers, timeout=60,
                        json={"projectId": project_id, "runCommand": run_command, "title": "airflow"}).json()["job"]
    while True:
        job = requests.get(f"{base}/api/jobs/beta/jobs/{job['id']}", headers=headers, timeout=60).json()["job"]
        if job["status"]["isCompleted"]:
            break
        time.sleep(30)
    if job["status"]["executionStatus"] != "Succeeded":
        logs = requests.get(f"{base}/api/jobs/beta/jobs/{job['id']}/logs", headers=headers,
                            params={"logType": "stdErr"}, timeout=60).json()
        raise RuntimeError(f"Domino job {job['id']} {job['status']['executionStatus']}: {logs}")
    return job["commitDetails"]["outputCommitId"]
```

The returned commit id is the XCom value a downstream task can pass as `commitId` (DFS
projects) or use with `GET /api/projects/v1/projects/{projectId}/files/{commitId}/{path}/content`
to read a result file. Polling details: [JOBS-API-PATTERN.md](./JOBS-API-PATTERN.md).

## Result delivery

Airflow can also run **after** a Domino scheduled Job finished elsewhere: a sensor-style task
that lists Jobs (`GET /api/jobs/beta/jobs?projectId=...&statusFilter=completed`) and downloads the
newest result file with the files route above, then delivers it (email, S3, a warehouse load).
The batch-scoring page on docs.domino.ai names this as the way to automate result delivery.
