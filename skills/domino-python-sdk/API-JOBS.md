# Domino Jobs API

Start, list, inspect and poll Jobs with the Public API. Every route and field below is in
both published specs (https://docs.domino.ai/api-specs/6.3/public-api.json and
https://docs.domino.ai/api-specs/cloud/public-api.json) unless marked otherwise. Product
docs: https://docs.domino.ai/cloud/platform-capabilities/core-concepts/jobs/monitor-jobs.

## Authentication

Use the shared setup block (`base_url`, `headers`) from
[domino-api-intro](../domino-api-intro/SKILL.md#authentication). Inside a run,
`DOMINO_PROJECT_ID` is already set.

## Start a job

```
POST /api/jobs/v1/jobs
```

Request body (`projectId` and `runCommand` are the only required fields):

| Field | Type | Notes |
|-------|------|-------|
| `projectId` | string | **Required** |
| `runCommand` | string | **Required**. The command, for example `python train.py --epochs 100` |
| `title` | string | Name of the job as shown in the Jobs list |
| `hardwareTier` | string | Hardware tier **id** (for example `small-k8s`); project default when omitted. List ids with `GET /api/hardwaretiers/v1/hardwaretiers` (needs the ViewHardwareTiers permission) or python-domino `hardware_tiers_list()` (tiers usable by the project) |
| `environmentId` | string | Environment id; project default when omitted |
| `environmentRevisionSpec` | string | `ActiveRevision`, `LatestRevision` or `SomeRevision(<revisionId>)` |
| `commitId` | string | DFS commit to run against; defaults to the project's head. Applies only to the project's internal DFS history: it cannot pin a commit on a Git-based project's main repository (use `mainRepoGitRef` with `commitId` for that) |
| `mainRepoGitRef` | object | `{"refType": "head" | "branches" | "tags" | "commitId", "value": "..."}` (`refType` required; `value` for all but `head`). These are the spec's values for jobs; the project-repository `defaultRef` uses a different set |
| `externalVolumeMountIds` | string[] | External data volume ids |
| `netAppVolumeIds` | string[] | NetApp volume ids; see [netapp-volumes](../netapp-volumes/API-NETAPP-VOLUMES.md) |
| `snapshotDatasetsOnCompletion`, `snapshotNetAppVolumesOnCompletion` | boolean | Snapshot mounted datasets / volumes when the job ends |
| `computeCluster` | object | `clusterType` (`dask`, `mpi`, `ray`, `slurm`, `spark`), `computeEnvironmentId`, `workerCount`, `workerHardwareTier` required; optional `masterHardwareTierId`, `maxWorkerCount`, `workerStorageMB`, `computeEnvironmentRevisionSpec` |
| `capacityType` | string | |

There is no `hardwareTierId`, `isDirectHardwareTierId` or `commandToRun` field.

```python
response = requests.post(
    f"{base_url}/api/jobs/v1/jobs",
    headers=headers,
    json={
        "projectId": os.environ["DOMINO_PROJECT_ID"],
        "runCommand": "python train.py --epochs 100 --lr 0.001",
        "title": "Hyperparameter experiment",
        "hardwareTier": "small-k8s",
    },
)
response.raise_for_status()
job = response.json()["job"]
print(job["id"], job["number"], job["status"]["executionStatus"])
```

Response (`200`): `{"job": {...}, "metadata": {"requestId", "notices"}}`. The job object
has `id`, `number`, `title`, `runCommand`, `status` (`executionStatus`, `isCompleted`,
`isArchived`, `isScheduled`), `stageTimes`, `commitDetails` (`inputCommitId`,
`outputCommitId`), `datasetMounts`, `externalVolumeMounts`, `netAppVolumeMounts`,
`gitRepos`, `projects`, `dominoStats`, `tags`, `goalIds`, `startedById`,
`computeCluster`, `usage`.

## List jobs

```
GET /api/jobs/beta/jobs?projectId=<id>
```

| Parameter | Type | Notes |
|-----------|------|-------|
| `projectId` | string | **Required** |
| `offset`, `limit` | integer | Pagination |
| `statusFilter` | string | `all`, `queued`, `running`, `completed`, `archived`, `active` |
| `sortBy` | string | `number`, `title`, `command`, `startedTime`, `duration`, `status`, `user`, `commentCount`, `dominoStatsField` |
| `ascending`, `showArchived` | boolean | |
| `tagFilter`, `dominoStatsSortFieldName` | string | |

```python
response = requests.get(
    f"{base_url}/api/jobs/beta/jobs",
    headers=headers,
    params={"projectId": os.environ["DOMINO_PROJECT_ID"], "statusFilter": "running", "limit": 50},
)
for job in response.json()["jobs"]:
    print(job["id"], job["status"]["executionStatus"], job["runCommand"])
```

Response: `{"jobs": [...], "metadata": {"requestId", "notices", "offset", "limit", "totalCount"}}`.
The `notices` array carries `"Beta endpoint with known limitations"`.

## Get job details

```
GET /api/jobs/beta/jobs/{jobId}
```

Returns `{"job": {...}, "metadata": {...}}` with the same job object as above.

## Get job logs

```
GET /api/jobs/beta/jobs/{jobId}/logs
```

| Parameter | Notes |
|-----------|-------|
| `logType` | `stdOut`, `stdErr`, `prepareOutput` or `complete` (case-insensitive) |
| `limit` | Max log lines; never more than 10,000 per call |
| `latestTimeNano` | Epoch nanoseconds to start from; take it from `metadata.pagination.latestTimeNano` of the previous page |

```python
logs = requests.get(f"{base_url}/api/jobs/beta/jobs/{job_id}/logs",
                    headers=headers, params={"logType": "stdOut", "limit": 500}).json()
for entry in logs["logs"]["logContent"]:          # each entry: {"log", "logType", "size", ...}
    print(entry["log"])
print("complete:", logs["logs"]["isComplete"])
```

## Poll for completion

```python
import time

def wait_for_job(job_id, timeout=3600, poll_interval=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = requests.get(f"{base_url}/api/jobs/beta/jobs/{job_id}", headers=headers).json()["job"]
        if job["status"]["isCompleted"]:
            return job
        print(job_id, job["status"]["executionStatus"])
        time.sleep(poll_interval)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

job = wait_for_job(job["id"])
print("final:", job["status"]["executionStatus"])   # Succeeded, Failed, Stopped or Error
```

Terminal outcomes per https://docs.domino.ai/cloud/platform-capabilities/core-concepts/jobs/job-states:
`Succeeded`, `Stopped` (manually stopped), `Failed` (a problem with your code) and
`Error` (a problem outside your code). Treat anything other than `Succeeded` as a
failure in automation.

## Stop a job

The Public API has no stop route. Options:

- python-domino `domino.job_stop(job_id, commit_results=True)`; it calls
  `POST /v4/jobs/stop` (internal API, may change between Domino versions). See
  [SDK-EXAMPLES.md](./SDK-EXAMPLES.md#jobs).
- The Jobs page in the Domino UI.

## Job tags

```
POST   /api/jobs/v1/jobs/{jobId}/tags                          body: {"tagName": "best-model", "projectId": "<project-id>"}
DELETE /api/jobs/v1/jobs/{jobId}/tags/{tagId}?projectId=<project-id>
```

`tagName` and `projectId` are required on create; `projectId` is a required query
parameter on delete. The create response is `{"tag": {"id", "name", "createdAt", "creatorId"}, "metadata"}`.

## Job goals

```
GET    /api/jobs/v1/goals?jobId=<jobId>                  goals linked to a job
POST   /api/jobs/v1/goals?jobId=<jobId>                  body: {"goalId": "<goal-id>"}
DELETE /api/jobs/v1/goals/{goalId}?jobId=<jobId>
```

`jobId` is a query parameter on all three. Project goals themselves are managed in
[API-PROJECTS.md](./API-PROJECTS.md#project-goals).

## Job defaults (Domino Cloud only)

```
POST /api/jobs/v1/projects/{projectId}/job-defaults
```

Present in the Cloud spec only (6.4.0 and later). Send the fields you intend to post to
`POST /api/jobs/v1/jobs` (all optional) and receive `jobDefaults` with the resolved
hardware tier, environment, commit, dataset and NetApp snapshot pins. On Domino 6.3 there
is no public equivalent; the UI resolves defaults.

## Scheduled jobs

Neither published spec has a scheduled-jobs route. Create and edit schedules in the UI:
https://docs.domino.ai/cloud/platform-capabilities/core-concepts/jobs/schedule-a-job.
The internal route the UI uses (`/v4/projects/{projectId}/scheduledjobs`) is Domino
Internal API, may change between Domino versions, and takes `command`, not `runCommand`;
confirm its body in your deployment's `/docs/openapi/openapi-internal.json` before using it.

## python-domino

`job_start`, `job_status`, `job_stop`, `jobs_list` and `job_start_blocking` wrap the
internal `/v4/jobs` routes with Python-side validation. Signatures and examples:
[SDK-EXAMPLES.md](./SDK-EXAMPLES.md#jobs). The SDK takes `hardware_tier_id` and
`command`; the Public API takes `hardwareTier` and `runCommand`.
