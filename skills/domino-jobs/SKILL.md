---
name: domino-jobs
description: Create, run, and manage Domino Jobs - batch executions for scripts, training, and data processing. Covers starting a Job from the UI, CLI or REST API, pinning the commit after an upload, hardware tiers and environments, scheduled Jobs with Quartz cron, checking status and logs through the Jobs API, stopping Jobs, results and notifications. Use when running batch workloads, scheduling recurring tasks, or automating training pipelines.
compatibility: Domino 6.3 and Domino Cloud. Requires DOMINO_API_HOST; in a run use DOMINO_API_PROXY or the localhost:8899 access-token endpoint, outside a run a Personal Access Token.
---

# Domino Jobs

Applies to Domino 6.3 and Domino Cloud.

A Job runs one command to completion in its own container on a hardware tier, recording the Project files, environment revision, data mounts and inputs for reproducibility. Interactive work: [domino-workspaces](../domino-workspaces/SKILL.md); web forms that start Jobs: [domino-launchers](../domino-launchers/SKILL.md).

Authentication ([domino-api-intro](../domino-api-intro/SKILL.md)): in a run `$DOMINO_API_PROXY` with no `Authorization` header; outside, `$DOMINO_API_HOST` with a Personal Access Token or service-account bearer token.

## Start a Job

**UI**: **Jobs > Run**. Enter the **Command or File Name** with arguments (`train.py --epochs 100`), pick the environment and revision and volume size, **Next**, pick the hardware tier, optionally a compute cluster ([domino-distributed-computing](../domino-distributed-computing/SKILL.md)), then start.

**CLI**: `domino run <file> [args]` (`--wait` blocks, `--direct "<shell command>"`) from a logged-in Domino CLI Project directory.

**REST**: `POST /api/jobs/v1/jobs` (both specs). Only `projectId` and `runCommand` are required; everything else defaults from the Project. A misspelt field (`hardwareTierId`) or an unknown `hardwareTier` id still returns 200 and the Job silently runs on the default tier; verify below.

**Right after uploading files** (DFS Projects): the DFS head can lag an upload by a few seconds, so a Job started without `commitId` can run the previous commit. The MCP tool `run_domino_job` pins the commit by itself after the MCP upload tools (which return `commitId`). Over REST, pin `commitId` to the commit the upload returned, or read `GET /api/projects/beta/projects/{projectId}/commits/latest` and confirm `GET /api/projects/v1/projects/{projectId}/files/{commitId}/{path}/content` returns 200 for your file before starting ([code](./SCRIPT-PATTERNS.md#pin-the-commit-after-an-upload)). Git-based Projects pin code with `mainRepoGitRef` instead.

```python
import os, requests

r = requests.post(f"{os.environ['DOMINO_API_PROXY']}/api/jobs/v1/jobs", json={
    "projectId": os.environ["DOMINO_PROJECT_ID"],
    "runCommand": "python train.py --epochs 100",
    "title": "Training run",
    # "commitId": "<DFS commit>",                 # pin after an upload; DFS history only
    # "hardwareTier": "small-k8s",                # tier id from GET /api/hardwaretiers/v1/hardwaretiers
    # "environmentId": "<id>", "environmentRevisionSpec": "ActiveRevision",
    # "mainRepoGitRef": {"refType": "branches", "value": "main"},   # Git-based; refType: head | commitId | tags | branches (not "branch")
    # also: computeCluster, netAppVolumeIds, externalVolumeMountIds
})
r.raise_for_status()
job = r.json()["job"]                              # response: {"job": {...}, "metadata": {...}}
print(job["id"], job["number"], job["status"]["executionStatus"])
```

Tags: `POST /api/jobs/v1/jobs/{jobId}/tags` `{"projectId", "tagName"}`; `DELETE .../tags/{tagId}?projectId=...` (query parameter required).

### Which path applies

Read `GET $DOMINO_API_HOST/version`. On `6.3.x` use only the routes above. On 6.4 and later (Domino Cloud today) `POST /api/jobs/v1/projects/{projectId}/job-defaults` also exists: send `{}` or overrides (the start-Job resource fields plus snapshot and volume-size fields) to get the resolved configuration a Job would run with, without starting one (`404` = absent).

## Monitor a Job

Both specs; responses carry a beta notice in `metadata.notices`.

- List: `GET /api/jobs/beta/jobs?projectId=...&statusFilter=all|queued|running|completed|archived|active&limit=&offset=` -> `{"jobs": [...], "metadata": {..., "totalCount"}}`.
- Details: `GET /api/jobs/beta/jobs/{jobId}` -> `job.status.executionStatus` (see the job-states docs), `status.isCompleted`, `stageTimes.{submissionTime,startTime,completedTime}`, `commitDetails.{inputCommitId,outputCommitId}`, `usage`, `computeCluster`, `runLauncherId`.
- Logs: `GET /api/jobs/beta/jobs/{jobId}/logs?logType=stdOut|stdErr|prepareOutput|complete&limit=1000&latestTimeNano=...` -> `logs.logContent[].{timestamp,logType,log}`, `logs.isComplete`, `metadata.pagination.latestTimeNano` for the next page.
- Verify what a Job ran on: the public Job object omits tier and environment; use the Job **Details** tab or `GET /v4/jobs/{jobId}/runtimeExecutionDetails` -> `hardwareTier.id`, `environment.environmentId` (internal API, may change between Domino versions; python-domino `job_runtime_execution_details(job_id)` wraps it).

## Stop, re-run, archive

- Stop: **Jobs > Active**, select, **Stop**. The Public API has no stop route; the Internal API has `POST /v4/jobs/stop` with `{"projectId", "jobId", "commitResults"}` (internal API, may change between Domino versions; python-domino `job_stop(job_id, commit_results=True)`, [domino-python-sdk](../domino-python-sdk/SKILL.md)).
- Re-run: select a Job > **Re-Run with Original Version** or **Re-Run with Current Version**.
- Archive hides completed Jobs; `showArchived=true` lists them.

## Scheduled Jobs

Configured only in the UI: **Jobs > Schedules > Schedule a Job**. The Public API has no scheduled-Job routes; `/v4/projects/{projectId}/scheduledjobs` exists (internal API, may change between Domino versions). Fields: the Job fields plus a schedule, **Run sequentially** (no overlapping runs), **Notify emails**, **Update Domino endpoint**. No pause exists: set a far-future start to suspend.

**Schedule** is a repeat interval or a **Quartz CronTrigger** expression (`sec min hour day-of-month month day-of-week [year]`, not crontab): seconds first, `?` in exactly one of the two day fields, day-of-week `1-7` or `SUN-SAT` (1 = SUN).

| Schedule | Expression |
|---|---|
| Every hour on the hour | `0 0 * * * ?` |
| Daily at 00:00 | `0 0 0 * * ?` |
| Mondays at 09:00 | `0 0 9 ? * MON` |

Special characters (`-`, `/`, `L`, `W`, `#`): https://www.quartz-scheduler.org/documentation/quartz-2.3.0/tutorials/crontrigger.html

## Results and notifications

Files created or modified under the Project files during the run are results. Write `dominostats.json` at the Project root for dashboard columns, `email.html` for a custom success email, `.dominoresults` to choose what is shown and attached; `.dominoignore` drops files from the revision. Success emails: Project **Settings > Access and Sharing**.

## Troubleshooting

- `can't open file` right after an upload: the Job ran the previous DFS commit. Pin `commitId` as above and re-run.
- `400` from `POST /api/jobs/v1/jobs`: a `commitId` not in the Project's DFS history (use `mainRepoGitRef` for Git) or an environment the Project cannot use. A wrong tier id gives no error: check the runtime details.
- Stuck in Queued: tier capacity or the per-user execution limit; Building/Pulling: the environment is still building.
- Failed = non-zero exit (`stdErr` logs); Error = platform problem (`prepareOutput` logs, support bundle).

## Reference files and docs

- [SCRIPT-PATTERNS.md](./SCRIPT-PATTERNS.md): commands, environment variables, output locations, commit pinning, logs, best practices.
- https://docs.domino.ai/cloud/platform-capabilities/core-concepts/jobs/create-and-run-jobs, `.../schedule-a-job`, `.../monitor-jobs`, `.../job-states` (same paths under `/6.3/`).
