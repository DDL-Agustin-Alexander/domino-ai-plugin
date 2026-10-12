---
type: llm
---

PASS if the code constructs `Domino("alice/churn")` (a project argument, with no `api_key=`; relying on the API proxy / injected environment inside the workspace), starts the job with `job_start`, `job_start_blocking`, `runs_start` or `runs_start_blocking`, and waits using `job_start_blocking`/`runs_start_blocking` or by polling `job_status`/`runs_status`.
FAIL if it calls python-domino methods that do not exist (for example runs_wait, runs_get_logs, runs_stop, workspace_start), passes an API key, or constructs `Domino()` with no project.
