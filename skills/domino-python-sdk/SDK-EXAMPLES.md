# python-domino: supported methods and examples

Every method below exists in `domino/domino.py` at release 2.2.0 of
https://github.com/dominodatalab/python-domino (`dominodatalab` on PyPI). Names, argument
names and required arguments are taken from the source, not from memory. Methods marked
**legacy** call the pre-Jobs v1 Runs API and are kept only for existing scripts.

Client setup and authentication: [SKILL.md](./SKILL.md#authentication). Never pass
`api_key=`.

```python
import os
import requests
from domino import Domino

project = f"{os.environ['DOMINO_PROJECT_OWNER']}/{os.environ['DOMINO_PROJECT_NAME']}"

if os.environ.get("DOMINO_API_PROXY"):
    # Inside a Domino execution with the API proxy: the client picks DOMINO_API_HOST and
    # DOMINO_API_PROXY up from the environment.
    domino = Domino(project)
elif os.environ.get("DOMINO_RUN_ID"):
    # Inside a run without the proxy: pass the short-lived token explicitly. Without it the
    # client falls back to DOMINO_TOKEN_FILE and then the deprecated DOMINO_USER_API_KEY.
    domino = Domino(project, auth_token=requests.get("http://localhost:8899/access-token").text.strip())
else:
    # Outside Domino: deployment URL plus a PAT or service account token
    domino = Domino("owner/project-name", host=os.environ["DOMINO_API_HOST"],
                    auth_token=os.environ["DOMINO_API_TOKEN"])
```

`domino.authenticate(auth_token=...)` re-authenticates an existing client, which is how a
long-running script refreshes the short-lived access token. The client is bound to one
project (`owner/project-name`); `domino.project_id` resolves its id. Most methods call the
Domino Internal API (`/v4/...`, `/v1/projects/...`) on behalf of that project.

## Method reference

Required arguments have no default. `**kwargs` on the legacy methods accept the old
camelCase names (`runId`, `commitId`).

### Jobs

| Method | Notes |
|--------|-------|
| `job_start(command, commit_id=None, hardware_tier_id=None, hardware_tier_name=None, environment_id=None, on_demand_spark_cluster_properties=None, compute_cluster_properties=None, external_volume_mounts=None, title=None, main_repo_git_ref=None, branch=None)` | Returns the created job dict (`id`, `number`, ...). `hardware_tier_name` and `on_demand_spark_cluster_properties` are deprecated in the source; use `hardware_tier_id` and `compute_cluster_properties`. For Git-based projects pass `branch="main"` or `main_repo_git_ref={"type": "branches" or "tags", "value": "..."}` (master adds `"commitId"`); `commit_id` pins the DFS commit, not a git commit. Validates ids and raises `HardwareTierNotFoundException` / `EnvironmentNotFoundException`. |
| `job_start_blocking(poll_freq=5, max_poll_time=6000, ignore_exceptions=(RequestException,), **job_start_kwargs)` | Starts, polls `job_status` until `statuses.isCompleted`, prints the log, returns the final status dict. Raises `RunFailedException` only when `statuses.executionStatus == "Failed"`; it returns normally on `Stopped` and `Error`, so check `executionStatus == "Succeeded"` yourself. |
| `authenticate(api_key=None, auth_token=None, domino_token_file=None, api_proxy=None)` | Re-authenticate an existing client (refresh an expired short-lived token). |
| `job_status(job_id)` | Dict with `statuses.executionStatus` and `statuses.isCompleted` (plus job fields). |
| `job_stop(job_id, commit_results=True)` | Returns the raw `requests.Response`. |
| `jobs_list(project_id, order_by="number", sort_by="desc", page_size=None, page_no=1, show_archived="false", status="all", tag=None)` | Job history for a project id. |
| `job_restart(job_id, should_use_original_input_commit=True)` | |
| `job_runtime_execution_details(job_id)` | |
| `get_run_log(run_id, include_setup_log=True)` | Unified setup + stdout text for a job or run id. |
| `runs_stdout(run_id)` | Stdout only, HTML stripped. |

Legacy v1 Runs API (source docstring: "For new work, prefer job_start()"):
`runs_start(command, is_direct=False, commit_id=None, title=None, tier=None, publish_api_endpoint=None)`,
`runs_start_blocking(...)`, `runs_status(run_id)`, `runs_list()`, `get_run_info(run_id)`,
`run_stop(run_id, save_changes=True)` (logs "Use job_stop method instead" and delegates to it).
`runs_start` takes `tier` (a hardware tier name), not `hardware_tier_name` or `environment_id`.

### Files and commits

| Method | Notes |
|--------|-------|
| `files_list(commit_id=None, path="/")` | Lists project files at a commit. Pass `commit_id` (from `commits_list()`): the default `None` is concatenated into the URL and raises `TypeError`. |
| `files_upload(path, file)` | `path` inside the project (leading `/` added if missing); `file` is an open binary file object. Uploads one file. |
| `files_download(path, commit_id=None)` | Resolves the latest commit when `commit_id` is omitted and returns the raw response stream from `blobs_get_v2`; read it with `.read()` / `.data`. |
| `blobs_get_v2(path, commit_id, project_id)` | Public API `GET /api/projects/v1/projects/{projectId}/files/{commitId}/{path}/content`. `blobs_get(key)` is deprecated. |
| `commits_list()` | Commits of the project; `[0]` is the latest. |

### Projects, collaborators, project tags

| Method | Notes |
|--------|-------|
| `project_create(project_name, owner_username=None)` | Returns a `requests.Response`, not JSON. |
| `project_create_v4(project_name, owner_id=None, owner_username=None, description="", collaborators=None, tags=None, billing_tag=None, visibility=ProjectVisibility.PUBLIC)` | `ProjectVisibility` from `domino.domino_enums` (`PRIVATE`, `PUBLIC`, `SEARCHABLE`). |
| `projects_list(relationship="Owned", show_completed=False)` | `relationship` in `Owned`, `Collaborating`, `Suggesting`, `Popular`. Returns a list of project dicts. |
| `project_archive(project_name)` | Raises `ProjectNotFoundException`. |
| `fork_project(target_name)` | |
| `collaborators_get()`, `collaborators_add(username_or_email, message="")`, `collaborators_remove(username_or_email)` | |
| `tags_list(project_id=None)`, `tags_add(tags: list, project_id=None)`, `tags_remove(tag_name, project_id=None)`, `tag_get_id(tag_name, project_id=None)` | Legacy project tags, not the taxonomy tags in [tags-and-properties](../tags-and-properties/SKILL.md). |

### Datasets

| Method | Notes |
|--------|-------|
| `datasets_list(project_id=None)`, `datasets_ids(project_id)`, `datasets_names(project_id)` | |
| `datasets_create(dataset_name, dataset_description)` | Both arguments required. Raises `DatasetExistsException` on a duplicate name. |
| `datasets_details(dataset_id)`, `datasets_update_details(dataset_id, dataset_name=None, dataset_description=None)`, `datasets_remove(dataset_ids: list)` | |
| `datasets_upload_files(dataset_id, local_path_to_file_or_directory, file_upload_setting=None, max_workers=None, target_chunk_size=None, target_relative_path=None)` | Chunked, resumable upload of a file or directory into the dataset's read-write snapshot; returns the local path it uploaded. |

There is no `datasets_snapshot` or `datasets_tag` method. Snapshot and tag routes are REST:
[API-DATASETS.md](./API-DATASETS.md).

### Environments and hardware tiers

| Method | Notes |
|--------|-------|
| `environments_list()`, `get_environment(environment_id)`, `get_default_environment()` | `get_environment` calls the Public API `GET /api/environments/v1/environments/{id}`. |
| `create_environment(name, visibility, dockerfile_instructions="", environment_variables=None, base_image="", post_run_script="", post_setup_script="", pre_run_script="", pre_setup_script="", skip_cache=False, summary="", supported_clusters=None, tags=None, use_vpn=False, workspace_tools=None, add_base_dependencies=True, description="", is_restricted=False, organization_owner_id=None)` | Public API `POST /api/environments/beta/environments` (current on 6.3; deprecated on Cloud in favour of v2, which the SDK does not wrap). |
| `create_environment_revision(environment_id, dockerfile_instructions="", ...)` | Same optional build fields as above; same beta route caveat. |
| `restrict_environment_revision(environment_id, revision_id)`, `archive_environment(environment_id)` | |
| `hardware_tiers_list()`, `get_hardware_tier_id_from_name(hardware_tier_name)` | Tiers usable by the client's project. |

### Model APIs and apps

| Method | Notes |
|--------|-------|
| `models_list()` | Model APIs in the project. |
| `model_publish(file, function, environment_id, name, description, files_to_exclude=None)` | All five leading arguments required. Returns the created Model API JSON. |
| `model_versions_get(model_id)`, `model_version_publish(model_id, file, function, environment_id, description, files_to_exclude=None)` | |
| `model_version_export(...)`, `model_version_sagemaker_export(...)`, `model_version_export_status(model_export_id)`, `model_version_export_logs(model_export_id)` | Image export to a registry. |
| `app_publish(unpublish_running_apps=True, hardware_tier_id=None, environment_id=None, external_volume_mount_ids=None, commit_id=None, branch=None, app_id=None)`, `app_unpublish(app_id=None)`, `app_get_status(app_id)`, `app_id` (property) | Legacy app start/stop; new automation uses the Public API in [domino-apps](../domino-apps/API-APPS.md). |

Budgets and billing tags (`budget_*`, `billing_tag*`, `project_billing_tag*`,
`projects_by_billing_tag`) and `custom_metrics_client()` (model monitoring custom
metrics) exist as well; see the source for signatures.

### Methods that do not exist

Do not call `runs_wait`, `runs_get_logs`, `runs_stop`, `runs_get_results`, `workspace_start`,
`workspace_stop`, `datasets_snapshot`, `datasets_tag`, `project_info`, `project_get`,
`project_update`, `environment_get` or `model_get`. None is in python-domino. Use the
methods above or the REST routes in the API-*.md files.

## Examples

### Start a job and wait for it

```python
job = domino.job_start(
    command="python train.py --epochs 100",
    hardware_tier_id="small-k8s",          # from hardware_tiers_list()
    environment_id="<environment-id>",     # optional; project default when omitted
    title="Training run",
)
job_id = job["id"]

status = domino.job_status(job_id)
print(status["statuses"]["executionStatus"], status["statuses"]["isCompleted"])

# Or block until completion. RunFailedException is raised only for "Failed"; "Stopped" and
# "Error" return normally, so always check the final status.
final = domino.job_start_blocking(command="python train.py", hardware_tier_id="small-k8s")
if final["statuses"]["executionStatus"] != "Succeeded":
    raise RuntimeError(f"job ended with {final['statuses']['executionStatus']}")
print(domino.get_run_log(final["id"], include_setup_log=False))
```

### Stop a job

```python
domino.job_stop(job_id, commit_results=True)
```

### Parameter sweep

```python
job_ids = [
    domino.job_start(command=f"python train.py --lr {lr}", hardware_tier_id="small-k8s")["id"]
    for lr in (0.01, 0.001, 0.0001)
]
import time
while True:
    statuses = {j: domino.job_status(j)["statuses"] for j in job_ids}
    if all(s["isCompleted"] for s in statuses.values()):
        break
    time.sleep(30)
for j, s in statuses.items():
    print(j, s["executionStatus"])
```

### Files

```python
with open("data/local.csv", "rb") as fh:
    domino.files_upload("/data/local.csv", fh)

latest_commit = domino.commits_list()[0]["id"]
for f in domino.files_list(commit_id=latest_commit, path="/"):
    print(f)

content = domino.files_download("/results/output.csv").read()
```

### Datasets

```python
dataset = domino.datasets_create("training-data", "Preprocessed training data")
dataset_id = dataset["datasetId"]            # key used by the SDK's own integration tests
domino.datasets_upload_files(dataset_id, "./processed", target_relative_path="v1")
for ds in domino.datasets_list(domino.project_id):
    print(ds)
```

### Environments

```python
for env in domino.environments_list():
    print(env)
env = domino.get_environment("<environment-id>")
rev = domino.create_environment_revision("<environment-id>",
                                         dockerfile_instructions="RUN pip install pandas==2.2.2")
```

### Publish a Model API

```python
model = domino.model_publish(
    file="model.py", function="predict", environment_id="<environment-id>",
    name="my-classifier", description="Classification model",
)
model_id = model["data"]["_id"]                      # shape used by the SDK's own tests
versions = domino.model_versions_get(model_id)["data"]
latest_version_id = versions[0]["_id"]
```

`model_publish` posts to `/v1/models` (internal API, may change between Domino versions);
the Public API equivalent is `POST /api/modelServing/v1/modelApis`
([API-MODELS.md](./API-MODELS.md)).

### CI/CD trigger (outside Domino)

```python
import os, sys
from domino import Domino
from domino.exceptions import RunFailedException

domino = Domino("team/ml-project", host=os.environ["DOMINO_API_HOST"],
                auth_token=os.environ["DOMINO_API_TOKEN"])   # service account token
try:
    final = domino.job_start_blocking(command="python train.py", hardware_tier_id="small-k8s")
except RunFailedException as exc:               # executionStatus == "Failed"
    print(exc)
    sys.exit(1)
status = final["statuses"]["executionStatus"]
if status != "Succeeded":                       # "Stopped" and "Error" do not raise
    print(f"Training did not succeed: {status}")
    sys.exit(1)
print("Training succeeded")
```

## Error handling

`domino.exceptions` defines `DominoException` and subclasses: `RunFailedException`,
`RunNotFoundException`, `ProjectNotFoundException`, `DatasetNotFoundException`,
`DatasetExistsException`, `EnvironmentNotFoundException`, `HardwareTierNotFoundException`,
`CommitNotFoundException`, `UserNotFoundException`, `MalformedInputException`,
`MissingRequiredFieldException`, `UnsupportedFieldException`,
`UnsupportedOperationException`, `ReloginRequiredException`. HTTP failures surface as
`requests.exceptions.HTTPError` from the request manager, except a `409`, which it
converts to `ReloginRequiredException` ("Temporary credentials expired").

```python
from domino.exceptions import DominoException
import requests

try:
    job = domino.job_start(command="python train.py", hardware_tier_id="small-k8s")
except DominoException as exc:        # validation: unknown tier, environment, commit
    print(f"Domino error: {exc}")
except requests.exceptions.HTTPError as exc:
    print(f"HTTP {exc.response.status_code}: {exc.response.text}")
```

Set `DOMINO_LOG_LEVEL=DEBUG` to log every request the client makes.

## Domino Data API

Data source queries, dataset file access and training sets use the separate
`domino_data` package (`pip install "dominodatalab[data]"`; `domino.data_sources` and
`domino.training_sets` re-export it). See [domino-data-sdk](../domino-data-sdk/SKILL.md).
