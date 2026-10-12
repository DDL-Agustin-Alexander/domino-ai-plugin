---
name: domino-jobs
description: Create, run, and manage Domino Jobs - batch executions for scripts, training, and data processing. Covers starting a Job from the UI, CLI or REST API, hardware tiers and environments, scheduled Jobs with Quartz cron, checking status and logs through the Jobs API, stopping Jobs, results and notifications. Use when running batch workloads, scheduling recurring tasks, or automating training pipelines. For the CLI itself use domino-cli; for Jobs from Airflow or Kubeflow use domino-airflow-kubeflow; for batch scoring with a model use domino-model-delivery.
compatibility: Domino 6.3 and Domino Cloud. Requires DOMINO_API_HOST; in a run use DOMINO_API_PROXY or the localhost:8899 access-token endpoint, outside a run a Personal Access Token.
---

# Domino Jobs

Applies to Domino 6.3 and Domino Cloud.

A Job runs one command to completion in its own container on a hardware tier, recording the Project files, environment revision, data mounts and inputs for reproducibility. Interactive work: [domino-workspaces](../domino-workspaces/SKILL.md); web forms that start Jobs: [domino-launchers](../domino-launchers/SKILL.md); batch scoring with a trained model: [domino-model-delivery](../domino-model-delivery/SKILL.md).

Authentication: [domino-api-intro](../domino-api-intro/SKILL.md). In a run call `$DOMINO_API_PROXY` with no `Authorization` header; outside a run call `$DOMINO_API_HOST` with a Personal Access Token or service-account bearer token.

## Start a Job

**UI**: **Jobs > Run**. Enter the **Command or File Name** with arguments (`train.py --epochs 100`), pick the environment and revision and volume size, **Next**, pick the hardware tier, optionally a compute cluster ([domino-distributed-computing](../domino-distributed-computing/SKILL.md)) and per-asset snapshot pins, then start.

**CLI**: `domino run <file> [args]` (`--wait` blocks, `--direct "<shell command>"`) from a logged-in Domino CLI Project directory; install, sign-in, all commands: [domino-cli](../domino-cli/SKILL.md).

**REST**: `POST /api/jobs/v1/jobs` (both specs). Only `projectId` and `runCommand` are required; everything else defaults from the Project. An unknown field (such as a misspelt `hardwareTierId`) or an unknown `hardwareTier` id still returns 200 and the Job silently runs on the Project default tier, so verify what a Job ran on (below).

```python
import os, requests

r = requests.post(f"{os.environ['DOMINO_API_PROXY']}/api/jobs/v1/jobs", json={
    "projectId": os.environ["DOMINO_PROJECT_ID"],
    "runCommand": "python train.py --epochs 100",
    "title": "Training run",
    # "hardwareTier": "small-k8s",   # tier id from GET /api/hardwaretiers/v1/hardwaretiers
    # "environmentId": "<id>", "environmentRevisionSpec": "ActiveRevision",
    # "mainRepoGitRef": {"refType": "branches", "value": "main"},   # Git-based; refType: head | commitId | tags | branches
    #     ("branch" is accepted, then the Job fails)
    # "commitId": "<DFS commit>",   # DFS history only, never a Git commit
    # also: computeCluster, netAppVolumeIds, externalVolumeMountIds, snapshotDatasetsOnCompletion
})
r.raise_for_status()
job = r.json()["job"]   # response: {"job": {...}, "metadata": {...}}
print(job["id"], job["number"], job["status"]["executionStatus"])
```

Tags: `POST /api/jobs/v1/jobs/{jobId}/tags` with `{"projectId", "tagName"}`; `DELETE .../tags/{tagId}?projectId=...` (the query parameter is required).

### Which path applies

Read `GET $DOMINO_API_HOST/version`. On `6.3.x` use only the routes above. On 6.4 and later (Domino Cloud today) `POST /api/jobs/v1/projects/{projectId}/job-defaults` also exists: send `{}` or overrides (the start-Job resource fields except `runCommand` and `title`, plus `datasetSnapshots`, `netAppVolumeSnapshots`, `volumeSizeGiB`, `importedGitRepoOverrides`) to get the resolved configuration a Job would run with, without starting one (`404` = absent).

## Monitor a Job

Both specs; responses carry a beta notice in `metadata.notices`.

- List: `GET /api/jobs/beta/jobs?projectId=...&statusFilter=all|queued|running|completed|archived|active&limit=&offset=&sortBy=&tagFilter=` -> `{"jobs": [...], "metadata": {..., "totalCount"}}`.
- Details: `GET /api/jobs/beta/jobs/{jobId}` -> `job.status.executionStatus` (`Queued` ... `Running`, `Succeeded`, `Stopped`, `Failed`, `Error`; full list in the job-states docs), `status.isCompleted`, `stageTimes.{submissionTime,startTime,completedTime}`, `commitDetails.{inputCommitId,outputCommitId}`, `usage`, `computeCluster`, `runLauncherId`.
- Logs: `GET /api/jobs/beta/jobs/{jobId}/logs?logType=stdOut|stdErr|prepareOutput|complete&limit=1000&latestTimeNano=...` -> `logs.logContent[].{timestamp,logType,log}`, `logs.isComplete`, `metadata.pagination.latestTimeNano` for the next page. Code: [SCRIPT-PATTERNS.md](./SCRIPT-PATTERNS.md#logs).
- Verify what a Job ran on: the public Job object omits tier and environment; use the Job **Details** tab or `GET /v4/jobs/{jobId}/runtimeExecutionDetails` -> `hardwareTier.id`, `environment.environmentId` (internal API, may change between Domino versions; python-domino `job_runtime_execution_details(job_id)` wraps it).

## Stop, re-run, archive

- Stop: **Jobs > Active**, select, **Stop**. The Public API has no stop route; the Internal API has `POST /v4/jobs/stop` with `{"projectId", "jobId", "commitResults"}` (internal API, may change between Domino versions), which is what python-domino `job_stop(job_id, commit_results=True)` calls ([domino-python-sdk](../domino-python-sdk/SKILL.md)).
- Re-run: select a Job > **Re-Run with Original Version** or **Re-Run with Current Version** (Git refs refresh only if the original ran from a branch).
- Archive hides completed Jobs; `showArchived=true` lists them.

## Scheduled Jobs

Configured only in the UI: **Jobs > Schedules > Schedule a Job**. The Public API has no scheduled-Job routes; `/v4/projects/{projectId}/scheduledjobs` exists (internal API, may change between Domino versions). Fields: name, Git ref, file and arguments, hardware tier, data mounts, environment and revision, optional cluster, schedule, **Run sequentially** (no overlapping runs), **Notify emails**, **Update Domino endpoint** (republish after success). No pause exists: set a far-future start to suspend.

**Schedule** is a repeat interval or a **Quartz CronTrigger** expression, not five-field crontab: six required fields plus an optional year, seconds first, and `?` in exactly one of day-of-month or day-of-week (`0 0 0 * * ?` daily at 00:00, `0 0 9 ? * MON` Mondays at 09:00). Field layout and special characters: [SCRIPT-PATTERNS.md](./SCRIPT-PATTERNS.md#quartz-cron-expressions).

Airflow or Kubeflow as the scheduler: [domino-airflow-kubeflow](../domino-airflow-kubeflow/SKILL.md).

## Results and notifications

Every file created or modified under the Project files during the run is a result. Write `dominostats.json` at the Project root for dashboard columns, `email.html` for a custom success email, `.dominoresults` to choose what is shown and attached; `.dominoignore` drops matching files from the revision entirely. Success emails: Project **Settings > Access and Sharing**. Paths, env vars, exit codes and script patterns: [SCRIPT-PATTERNS.md](./SCRIPT-PATTERNS.md).

## Troubleshooting

- `400` from `POST /api/jobs/v1/jobs`: a `commitId` not in the Project's DFS history (use `mainRepoGitRef` for Git) or an environment the Project cannot use. A wrong tier id gives no error: check the runtime details.
- Queued or Building, Failed vs Error, missing results: [SCRIPT-PATTERNS.md](./SCRIPT-PATTERNS.md#troubleshooting-failed-jobs).

## Reference files and docs

- [SCRIPT-PATTERNS.md](./SCRIPT-PATTERNS.md): commands, env vars, outputs, logs, script practices, Quartz cron, troubleshooting.
- https://docs.domino.ai/cloud/platform-capabilities/core-concepts/jobs/create-and-run-jobs, `.../schedule-a-job`, `.../monitor-jobs`, `.../job-states` (same paths under `/6.3/`).
