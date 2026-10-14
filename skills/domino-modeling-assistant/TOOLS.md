# Domino MCP server tools

Reference for the tools the bundled server (`domino_server`, `mcp-servers/domino_mcp_server/`) exposes. The server README in the plugin repository lists the Domino routes behind each tool. Upstream source: https://github.com/dominodatalab/domino_mcp_server

| Tool | Description |
|------|-------------|
| `get_domino_environment_info()` | Inside or outside Domino, project owner, name and id, Git-based or DFS, auth mode, what is missing |
| `run_domino_job(user_name, project_name, run_command, title, git_branch=None, hardware_tier=None, environment_id=None, wait_seconds=0)` | Start a Job with one command string; with `wait_seconds` waits on the server and returns the final status plus `results` |
| `check_domino_job_run_status(run_id, user_name=None, project_name=None, wait_seconds=0)` | Status (`Queued`, `Preparing`, `Running`, `Succeeded`, `Failed`, `Stopped`, ...) and `is_completed`; with `wait_seconds` waits until complete or the cap |
| `check_domino_job_run_results(run_id, user_name=None, project_name=None, log_type="stdOut")` | Job output; `log_type` is `stdOut`, `stdErr`, `prepareOutput` or `complete` |
| `open_web_browser(url)` | Open a URL in the default browser of the machine running the server; inside a Domino execution it returns `False` without doing anything |
| `list_domino_project_files(user_name, project_name, path="/")` | Files and subdirectories of one directory of a DFS project (not recursive) |
| `download_file_from_domino_project(...)` | File content at the latest commit: `content` for text, `content_base64` for binary; remembers the version for `smart_sync_file` |
| `upload_file_to_domino_project(..., file_content=None, overwrite=False, content_base64=None)` | Create a file of any type in a DFS project; replaces an existing one only with `overwrite=True` |
| `sync_local_file_to_domino(..., overwrite=False)` | Read a local file as bytes (model artifacts, images, text) and upload it unchanged (same overwrite rule) |
| `smart_sync_file(..., content=None, force_overwrite=False, content_base64=None)` | Upload of any file type with conflict detection; `no_change`, uploaded, or conflict with the remote content returned |

A job id and a run id are the same value, so `run_id` from `run_domino_job` goes straight into the status and results tools; `user_name` and `project_name` on those two are optional. File content is limited to 2 MiB per call; paths are project-relative.

## Waiting for a Job

Hosts block a standalone `sleep`, and a status call without `wait_seconds` returns at once, so waiting happens on the server:

- `run_domino_job(..., wait_seconds=300)` starts the Job, waits on the server, and when the Job completes adds `results` (the last 100 lines or 8,000 characters of stdout, `results_truncated` when cut) and the MLflow link if the output printed one.
- `check_domino_job_run_status(run_id, wait_seconds=300)` waits for an already-running Job and returns the last status with `waited_seconds`.
- One call waits at most **600 s**. Under Codex, whose tool calls end after 60 s by default, the server detects the client and caps a wait at **50 s**. When the cap is reached before the Job completes, the response has `is_completed` false and a `message` saying to call again: call `check_domino_job_run_status(run_id, wait_seconds=300)` again, as many times as needed. Never loop on status calls without `wait_seconds`, and never run shell `sleep`.
- After completion, read the full output with `check_domino_job_run_results` (`stdOut`; `stdErr` when the status is not `Succeeded`).

## Hardware tier and environment

`run_domino_job` accepts `hardware_tier` (an id such as `small-k8s`, or a name) and `environment_id` (id or name). Domino would silently run a Job on the project default for an unknown tier id, so the server validates both against the deployment before starting and an unknown value is an error listing what exists. Omit both to use the project defaults; `git_branch` runs a Git-based project on another branch (pushed commits only).

## Files: text and binary, DFS only

The file tools work on DFS (non-Git) projects only; for a Git-based project, commit and push, because Jobs run the repository, not uploaded files.

- Text travels as `content` (`smart_sync_file`, `download_file_from_domino_project`) or `file_content` (`upload_file_to_domino_project`).
- Binary files (model artifacts such as `.joblib` or `.pkl`, images) travel as `content_base64`; `sync_local_file_to_domino` reads the local file as bytes and uploads it unchanged, so it is the simplest way to ship an artifact.
- `smart_sync_file` compares the remote file with the version this session last saw: unchanged content is `no_change`; a remote file that changed since (or was never seen) is a **conflict**, returned with the remote content, and nothing is uploaded unless `force_overwrite=True`. `upload_file_to_domino_project` and `sync_local_file_to_domino` refuse to replace an existing, different file unless `overwrite=True`. Do not force an overwrite without telling the user what will be replaced.

Tool failures (missing variable, 401/403, unknown hardware tier or environment, conflict, file too large) come back as MCP tool errors whose message says what to fix; relay it to the user instead of retrying blindly.
