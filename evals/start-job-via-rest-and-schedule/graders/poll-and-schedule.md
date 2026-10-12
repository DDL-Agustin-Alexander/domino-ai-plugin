---
type: llm
---

PASS if ALL hold:
1. The job is started with POST to `/api/jobs/v1/jobs` using a JSON body that includes `projectId` and `runCommand` (not `commandToRun`).
2. Status is polled with `GET /api/jobs/beta/jobs/{jobId}` reading `status.executionStatus` (or python-domino's `job_status` / `job_start_blocking`), finishing on a terminal state such as Succeeded, Failed, Stopped or Error.
3. Authentication is `$DOMINO_API_PROXY` with no header or a bearer token from `http://localhost:8899/access-token`.
4. For the schedule question, the reply says scheduled Jobs are created in the Domino UI (Jobs > Schedules, Quartz cron) and that the public API has no endpoint for them. Mentioning an internal `/v4/...` route is acceptable only if it is labelled internal/unsupported and the UI is the recommendation.
FAIL if it presents a public `/api/...` route for creating scheduled jobs, polls `GET /api/jobs/v1/jobs/{id}` (that route does not exist; only the POST does), uses an API key header, or calls python-domino methods that do not exist (runs_wait, runs_get_logs, runs_stop).
