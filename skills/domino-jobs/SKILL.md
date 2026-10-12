---
name: domino-jobs
description: Create, run, and manage Domino Jobs - batch executions for scripts, training, and data processing. Covers starting a Job from the UI, CLI or REST API (POST /api/jobs/v1/jobs), hardware tiers and environments, scheduled Jobs with Quartz cron, checking status and logs through the Jobs API, stopping Jobs, results and notifications. Use when running batch workloads, scheduling recurring tasks, or automating training pipelines.
compatibility: Domino 6.3 and Domino Cloud. Requires DOMINO_API_HOST; in a run use DOMINO_API_PROXY or the localhost:8899 access-token endpoint, outside a run a Personal Access Token.
---

# Domino Jobs

Applies to Domino 6.3 and Domino Cloud.

A Job runs one command to completion in its own container on a hardware tier, recording the Project files, environment revision, data mounts and inputs for reproducibility. Interactive work: [domino-workspaces](../domino-workspaces/SKILL.md); web forms that start Jobs: [domino-launchers](../domino-launchers/SKILL.md).

Authentication: [domino-api-intro](../domino-api-intro/SKILL.md). Inside a run call `$DOMINO_API_PROXY` with no `Authorization` header; outside a run call `$DOMINO_API_HOST` with a Personal Access Token or service-account token as `Authorization: Bearer`.

## Start a Job

**UI**: **Jobs > Run**. Enter the **Command or File Name** with arguments (`train.py --epochs 100`), pick the environment and revision (the owner's active revision is recommended) and volume size, **Next**, pick the hardware tier, optionally a compute cluster ([domino-distributed-computing](../domino-distributed-computing/SKILL.md)) and per-asset Dataset or NetApp snapshot pins, then start. From **Code**, the gear menu > **Run** adds a title, a schedule and "publish after complete".

**CLI**: `domino run <file> [args]` (`--wait` blocks, `--direct "<shell command>"`) from a logged-in Domino CLI Project directory.

**REST**: `POST /api/jobs/v1/jobs` (both specs). Only `projectId` and `runCommand` are required; everything else defaults from the Project.

```python
import os, requests

r = requests.post(f"{os.environ['DOMINO_API_PROXY']}/api/jobs/v1/jobs", json={
    "projectId": os.environ["DOMINO_PROJECT_ID"],
    "runCommand": "python train.py --epochs 100",
    "title": "Training run",
    # "hardwareTier": "small-k8s",                # tier id from GET /api/hardwaretiers/v1/hardwaretiers
    # "environmentId": "<id>", "environmentRevisionSpec": "ActiveRevision",
    # "mainRepoGitRef": {"refType": "branches", "value": "main"},   # Git-based; refType: head | commitId | tags | branches
    # "commitId": "<DFS commit>",                 # DFS history only, never a Git commit
    # also: computeCluster, netAppVolumeIds, externalVolumeMountIds, snapshotDatasetsOnCompletion
})
r.raise_for_status()
job = r.json()["job"]                              # response: {"job": {...}, "metadata": {...}}
print(job["id"], job["number"], job["status"]["executionStatus"])
```

Tag a Job: `POST /api/jobs/v1/jobs/{jobId}/tags` with `{"projectId", "tagName"}`.

### Which path applies

`GET $DOMINO_API_HOST/version` returns `{"version": "6.3.x"}` (self-managed) or `"6.4.x"` (Domino Cloud). Only the Cloud spec has `POST /api/jobs/v1/projects/{projectId}/job-defaults`: send `{}` (or any subset of the start-Job fields as overrides) to get the resolved `hardwareTier`, `environmentId`, `environmentRevisionSpec`, `mainRepoGitRef`, `computeCluster`, volumes and snapshots a Job would run with, without starting one. On 6.3 read the Project settings instead.

## Monitor a Job

All three routes are in both specs; responses carry `metadata.notices` such as "Beta endpoint with known limitations".

- List: `GET /api/jobs/beta/jobs?projectId=...&statusFilter=all|queued|running|completed|archived|active&limit=25&offset=0&sortBy=number&tagFilter=...` -> `{"jobs": [...], "metadata": {..., "totalCount"}}`.
- Details: `GET /api/jobs/beta/jobs/{jobId}` -> `job.status.executionStatus` (Queued, Scheduled, Pending, Preparing, Building, Pulling, Running, Finishing, Succeeded, StopRequested, Stopping, Stopped, Failed, Error), `status.isCompleted`, `stageTimes.{submissionTime,startTime,completedTime}`, `commitDetails.{inputCommitId,outputCommitId}`, `usage`, `computeCluster`, `runLauncherId`.
- Logs: `GET /api/jobs/beta/jobs/{jobId}/logs?logType=stdOut|stdErr|prepareOutput|complete&limit=1000&latestTimeNano=...` -> `logs.logContent[].{timestamp,logType,log}`, `logs.isComplete`, `metadata.pagination.latestTimeNano` for the next page (max 10,000 lines per call). Code: [SCRIPT-PATTERNS.md](./SCRIPT-PATTERNS.md#logs).

## Stop, re-run, archive

- Stop: **Jobs > Active**, select, **Stop**. The Public API has no stop route; the Internal API has `POST /v4/jobs/stop` with `{"jobId", "commitResults"}` (internal API, may change between Domino versions), which is what python-domino `job_stop(job_id, commit_results=True)` calls ([domino-python-sdk](../domino-python-sdk/SKILL.md)).
- Re-run: select a Job > **Re-Run with Original Version** or **Re-Run with Current Version** (latest code, environment and imports; Git refs refresh only if the original ran from a branch).
- Archive hides completed Jobs; `showArchived=true` lists them.

## Scheduled Jobs

Configured only in the UI: **Jobs > Schedules > Schedule a Job**. The Public API has no scheduled-Job routes; the Internal API's `/v4/projects/{projectId}/scheduledjobs` routes may change between Domino versions. Fields: name, branch or commit (Git-based), file name with arguments, hardware tier and data mounts with snapshot pins, environment and revision, optional compute cluster, schedule, **Run sequentially** (wait for the previous run; otherwise overlapping runs are allowed), **Notify emails**, **Update Domino endpoint** (republish after success). Edit or delete under **Jobs > Schedules**; there is no pause, so set a far-future start to suspend.

**Schedule** is a repeat interval or a **Quartz CronTrigger** expression, not five-field crontab: six required fields plus an optional year, seconds first, and `?` in exactly one of day-of-month or day-of-week.

```
sec   min   hour  day-of-month  month         day-of-week                  [year]
0-59  0-59  0-23  1-31 or ?     1-12/JAN-DEC  1-7 or SUN-SAT (1=SUN) or ?
```

| Schedule | Expression |
|---|---|
| Every hour on the hour | `0 0 * * * ?` |
| Daily at 00:00 | `0 0 0 * * ?` |
| Mondays at 09:00 | `0 0 9 ? * MON` |
| First of every month | `0 0 0 1 * ?` |

Special characters (`-`, `/`, `L`, `W`, `#`): https://www.quartz-scheduler.org/documentation/quartz-2.3.0/tutorials/crontrigger.html

## Results and notifications

Every file created or modified under the Project files during the run is a result. Write `dominostats.json` at the Project root to add dashboard columns, `email.html` for a custom success email, `.dominoresults` or `.dominoignore` to choose what is shown and attached. Failure emails are on by default; success emails per collaborator under Project **Settings > Access and Sharing**. Paths, env vars, exit codes and script patterns: [SCRIPT-PATTERNS.md](./SCRIPT-PATTERNS.md).

## Troubleshooting

- `400` from `POST /api/jobs/v1/jobs`: a `commitId` not in the Project's DFS history (use `mainRepoGitRef` for Git), an unknown `hardwareTier` id, or an environment the Project cannot use.
- Stuck in Queued: tier capacity or the per-user execution limit; Building/Pulling: the environment is still building.
- Failed = non-zero exit from your command (`stdErr` logs); Error = platform problem (`prepareOutput` logs, support bundle).

## Reference files and docs

- [SCRIPT-PATTERNS.md](./SCRIPT-PATTERNS.md): commands, environment variables, output locations, logs, best practices.
- https://docs.domino.ai/cloud/platform-capabilities/core-concepts/jobs/create-and-run-jobs, `.../schedule-a-job`, `.../monitor-jobs`, `.../job-states` (same paths under `/6.3/`).
