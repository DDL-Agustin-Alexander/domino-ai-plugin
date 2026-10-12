# MCP server that wraps the Domino API for an AI coding assistant: start Jobs, read their status and
# logs, and read, upload and sync files of DFS (non-Git) projects. See README.md in this directory.
#
# Routes: everything that has a Public API equivalent in both published specs
# (https://docs.domino.ai/api-specs/6.3/public-api.json and .../cloud/public-api.json) uses it.
# Two operations have no public equivalent and keep their older routes; each is labelled at the
# point of use and listed in README.md:
#   - listing project files:  GET /v4/files/browseFiles, GET /v4/files/browseDirectories
#                             (Domino Internal API, may change between Domino versions)
#   - uploading a file:       PUT /v1/projects/{owner}/{project}/{path}
#                             (legacy API, not in any published spec)

from typing import Any, Callable, Dict, List
import functools
import hashlib
import os
import re
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import anyio
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------------------------

# Variables the server reads for its own configuration (not the ones Domino injects).
_CONFIG_VARS = ("DOMINO_HOST", "DOMINO_TOKEN", "DOMINO_API_KEY", "DOMINO_MCP_ENV_FILE",
                "DOMINO_INSECURE_HTTP")


def _drop_unset_placeholders(environ: Dict[str, str]) -> None:
    """Treat values a host passes for an unset variable as unset.

    Claude Code passes an unset ${VAR} through as the literal text "${VAR}"; Cursor may pass an
    unset ${env:NAME} as literal text or as an empty string. Either way the env-file fallback and
    the "not set" errors must still apply, so delete such values.
    """
    for name in [k for k, v in environ.items() if v.startswith("${")]:
        del environ[name]
    for name in _CONFIG_VARS:
        if environ.get(name) == "":
            del environ[name]


# Some hosts start stdio MCP servers with a minimal environment and give a plugin no way to
# forward more: Codex passes only HOME, LANG, LC_ALL, LOGNAME, PATH, SHELL and USER, and drops a
# plugin server that declares env_vars. Inside a Domino Workspace or Job the Domino variables are
# still set on the process that started the agent, so copy the ones this server reads from the
# nearest ancestor that has them. Linux only; the kernel allows reading the environment of
# processes owned by the same user.
_DOMINO_VARS = (
    "DOMINO_API_HOST", "DOMINO_API_PROXY", "DOMINO_PROJECT_ID", "DOMINO_PROJECT_NAME",
    "DOMINO_PROJECT_OWNER", "DOMINO_IS_GIT_BASED", "DOMINO_WORKING_DIR", "DOMINO_RUN_ID",
    "VSCODE_PROXY_URI",
)
_MARKER_VARS = ("DOMINO_API_PROXY", "DOMINO_API_HOST")


def _recover_domino_env(environ: Dict[str, str] | None = None, proc: str = "/proc",
                        start_pid: int | None = None, max_depth: int = 8) -> List[str]:
    """Copy Domino variables from the nearest ancestor process that has them.

    Returns the names that were recovered. Does nothing when a marker variable is already set or
    when `proc` is not a procfs directory (macOS, Windows).
    """
    env = os.environ if environ is None else environ
    if any(env.get(v) for v in _MARKER_VARS) or not os.path.isdir(proc):
        return []
    pid = os.getppid() if start_pid is None else start_pid
    for _ in range(max_depth):
        if pid <= 1:
            return []
        try:
            with open(f"{proc}/{pid}/environ", "rb") as f:
                parent = dict(kv.split(b"=", 1) for kv in f.read().split(b"\0") if b"=" in kv)
            with open(f"{proc}/{pid}/stat") as f:
                stat = f.read()
        except OSError:
            return []
        if any(v.encode() in parent for v in _MARKER_VARS):
            recovered = []
            for name in _DOMINO_VARS:
                value = parent.get(name.encode())
                if value is not None and name not in env:
                    env[name] = value.decode("utf-8", "replace")
                    recovered.append(name)
            return recovered
        # /proc/<pid>/stat is "pid (comm) state ppid ..."; comm may contain spaces.
        pid = int(stat.rsplit(")", 1)[1].split()[1])
    return []


def _env_file_path() -> Path:
    """Where the server reads DOMINO_HOST and DOMINO_TOKEN from when the host passes neither.

    `uv --directory` runs this server with the plugin directory as its working directory, so a
    `.env` next to the user's project is never found. Use one documented location instead:
    $DOMINO_MCP_ENV_FILE, else $XDG_CONFIG_HOME/domino-mcp-server/.env, else
    ~/.config/domino-mcp-server/.env.
    """
    explicit = os.environ.get("DOMINO_MCP_ENV_FILE")
    if explicit:
        return Path(explicit).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "domino-mcp-server" / ".env"


def _load_environment() -> None:
    """Import-time environment handling, in order: placeholders, ancestor recovery, env file."""
    _drop_unset_placeholders(os.environ)
    _recover_domino_env()
    load_dotenv(_env_file_path(), override=False)
    _drop_unset_placeholders(os.environ)
    if os.environ.get("DOMINO_API_KEY") and not os.environ.get("DOMINO_TOKEN"):
        print("domino_mcp_server: DOMINO_API_KEY is set but legacy API keys are not supported by "
              "this server. Set DOMINO_TOKEN to a Personal Access Token or service account token.",
              file=sys.stderr)


_load_environment()


class DominoError(Exception):
    """A tool-level failure with a message meant for the user and the model."""


def _auth_help() -> str:
    text = (
        "Outside a Domino execution set DOMINO_HOST to your Domino URL (for example "
        "https://domino.example.com) and DOMINO_TOKEN to a Personal Access Token (Account settings > "
        "Personal Access Token) or a service account token, either in the environment the MCP host "
        f"passes to this server or in the env file {_env_file_path()} (KEY=value lines, chmod 600; "
        "the file is read when the host strips the environment, as Codex does). Inside a Domino "
        "Workspace or Job the platform sets DOMINO_API_PROXY and no token is needed. See "
        "https://docs.domino.ai/cloud/reference/api/domino-api-authentication."
    )
    legacy_dotenv = Path(__file__).resolve().parent / ".env"
    if legacy_dotenv.is_file():
        text += f" Note: {legacy_dotenv} is no longer read; move its values to the env file above."
    return text


def _is_domino_workspace() -> bool:
    """True inside a Domino execution (Workspace, Job, App): the platform sets DOMINO_API_PROXY."""
    return bool(os.environ.get("DOMINO_API_PROXY"))


def _is_loopback(url: str) -> bool:
    host = urllib.parse.urlparse(url).hostname or ""
    return host in ("localhost", "127.0.0.1", "::1")


def _get_domino_host() -> str:
    """Base URL for API calls.

    Inside a Domino execution: $DOMINO_API_PROXY, which forwards to the platform and adds the
    starting user's token. Outside: DOMINO_HOST (or DOMINO_API_HOST) from the environment.
    """
    proxy = os.environ.get("DOMINO_API_PROXY")
    if proxy:
        return proxy.rstrip("/")
    host = (os.environ.get("DOMINO_HOST") or os.environ.get("DOMINO_API_HOST") or "").strip()
    if not host:
        raise DominoError("DOMINO_HOST is not set and this is not a Domino execution "
                          "(DOMINO_API_PROXY is not set). " + _auth_help())
    if host.startswith("http://") and not _is_loopback(host) \
            and os.environ.get("DOMINO_INSECURE_HTTP", "").lower() not in ("1", "true", "yes"):
        raise DominoError(f"DOMINO_HOST uses http://, which would send DOMINO_TOKEN in clear text. "
                          f"Use the https:// URL of your Domino deployment (set DOMINO_INSECURE_HTTP=true "
                          f"to allow http:// deliberately).")
    if not host.startswith(("http://", "https://")):
        raise DominoError("DOMINO_HOST must be a URL starting with https://")
    return host.rstrip("/")


_TOKEN_BAD_CHARS = re.compile(r"[\s\x00-\x1f\x7f]")


def _get_token() -> str | None:
    """DOMINO_TOKEN, stripped of surrounding whitespace; None when unset.

    Rejects a value with inner whitespace or control characters without echoing it, because
    `requests` would otherwise include the header value in its exception text.
    """
    raw = os.environ.get("DOMINO_TOKEN")
    if raw is None:
        return None
    token = raw.strip()
    if not token:
        return None
    if _TOKEN_BAD_CHARS.search(token):
        raise DominoError("DOMINO_TOKEN contains whitespace or control characters inside the value; "
                          "paste the token on one line with nothing else (the value is not shown here).")
    return token


def _get_auth_headers() -> Dict[str, str]:
    """Authentication headers for Domino API calls.

    Inside a Domino execution: none; the API proxy adds the user's token. Outside: DOMINO_TOKEN
    (Personal Access Token or service account token) as a bearer. Legacy API keys
    (DOMINO_API_KEY, X-Domino-Api-Key) are deprecated by Domino and not sent by this server.
    """
    if _is_domino_workspace():
        return {}
    token = _get_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    if os.environ.get("DOMINO_API_KEY"):
        raise DominoError("DOMINO_API_KEY is set, but legacy API keys (X-Domino-Api-Key) are "
                          "deprecated by Domino and not supported by this server. " + _auth_help())
    raise DominoError("DOMINO_TOKEN is not set. " + _auth_help())


def _auth_mode() -> str:
    if _is_domino_workspace():
        return "api_proxy"
    try:
        return "bearer_token" if _get_token() else "none"
    except DominoError:
        return "invalid_token"


def _redact(text: str) -> str:
    """Remove the bearer token from any text that may reach the model or a log."""
    try:
        token = _get_token()
    except DominoError:
        token = (os.environ.get("DOMINO_TOKEN") or "").strip() or None
    if token:
        text = text.replace(token, "<redacted>")
    return re.sub(r"(?i)bearer\s+[^\s'\"]+", "Bearer <redacted>", text)


def _get_external_host() -> str | None:
    """The user-facing Domino URL for links in results, or None when it is not known.

    Inside a Workspace only VSCODE_PROXY_URI carries it (DOMINO_API_HOST is the in-cluster URL
    and would give unreachable links). Outside, DOMINO_HOST is already the external URL.
    """
    if not _is_domino_workspace():
        try:
            return _get_domino_host()
        except DominoError:
            return None
    vpu = os.environ.get("VSCODE_PROXY_URI", "")
    if vpu:
        parsed = urllib.parse.urlparse(vpu)
        if parsed.scheme and parsed.hostname:
            return f"{parsed.scheme}://{parsed.hostname}"
    return None


def _env_flag(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value.strip().lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------------------------

_TIMEOUT = (10, 60)  # connect, read (seconds)


def _describe_http_error(method: str, path: str, resp: requests.Response) -> str:
    detail = ""
    try:
        body = resp.json()
        if isinstance(body, dict):
            detail = "; ".join(str(x) for x in (body.get("errors") or [])) or \
                str(body.get("message") or body.get("error") or "")
    except ValueError:
        detail = resp.text[:300]
    message = f"{method} {path} returned HTTP {resp.status_code}"
    if detail:
        message += f": {detail}"
    if resp.status_code in (401, 403) and not _is_domino_workspace():
        message += ". Check that DOMINO_TOKEN is a valid, unexpired Personal Access Token or " \
                   "service account token for DOMINO_HOST and that the token's user can access " \
                   "this project."
    return _redact(message)


def _api(method: str, path: str, *, params: Dict[str, Any] | None = None,
         json: Any = None, data: bytes | None = None, headers: Dict[str, str] | None = None,
         allow: tuple = ()) -> requests.Response:
    """One Domino API call. Raises DominoError with a readable, token-free message on failure."""
    url = f"{_get_domino_host()}{path}"
    hdrs = {**_get_auth_headers(), **(headers or {})}
    try:
        resp = requests.request(method, url, params=params, json=json, data=data, headers=hdrs,
                                timeout=_TIMEOUT)
    except Exception as e:  # requests exceptions can embed header values; never let them through raw
        raise DominoError(_redact(f"{method} {path} failed: {e}")) from None
    if resp.status_code in allow:
        return resp
    if resp.status_code >= 400:
        raise DominoError(_describe_http_error(method, path, resp))
    return resp


def _api_json(method: str, path: str, **kwargs: Any) -> Any:
    resp = _api(method, path, **kwargs)
    try:
        return resp.json()
    except ValueError:
        raise DominoError(f"{method} {path} returned a non-JSON response (HTTP {resp.status_code}). "
                          f"Check that DOMINO_HOST is the URL of the Domino deployment itself, not a "
                          f"login page or another site.") from None


def _threaded(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Run a blocking tool implementation in a worker thread so the stdio event loop stays free."""
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))
    return wrapper


# ---------------------------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------------------------

def _plugin_instructions() -> str | None:
    """The lead section of the plugin's always-on rules file, sent as MCP server instructions.

    rules/domino.md is the single source for the plugin's always-on guidance. Hosts that load it
    directly (a session-start hook, a context file, an always-on rule) get the whole file; hosts
    that only surface MCP server instructions, such as Codex, get its lead section: everything
    before the first "## " heading, without frontmatter, capped at 900 bytes.
    """
    rules = Path(__file__).resolve().parents[2] / "rules" / "domino.md"
    try:
        text = rules.read_text(encoding="utf-8")
    except OSError:
        return None
    text = text.replace("\r\n", "\n")
    # Same front-matter rule as scripts/lint-skills.py: exact "---" delimiter lines.
    match = re.match(r"\A---\n.*?\n---\n(.*)\Z", text, re.S)
    if match:
        text = match.group(1)
    lead = text.split("\n## ", 1)[0].strip()
    return lead.encode("utf-8")[:900].decode("utf-8", "ignore") or None


mcp = FastMCP("domino_server", instructions=_plugin_instructions())


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

def _validate_url_parameter(param_value: str, param_name: str) -> str:
    """Validate and URL-encode a single path segment (user name, project name, job id)."""
    if not param_value:
        raise DominoError(f"Invalid {param_name}: empty")
    if any(char in param_value for char in ['/', '\\', '?', '#', '&', '=', '%']):
        raise DominoError(f"Invalid {param_name}: '{param_value}' contains unsafe URL characters")
    return urllib.parse.quote(param_value, safe='')


def _normalize_project_path(file_path: str) -> str:
    """A project-relative file path: no leading slash, no '..', no URL metacharacters."""
    path = file_path.strip().replace("\\", "/").lstrip("/")
    if not path or path.endswith("/"):
        raise DominoError(f"Invalid file path {file_path!r}: must name a file")
    parts = path.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise DominoError(f"Invalid file path {file_path!r}: '..', '.' and empty segments are not allowed")
    if any(c in path for c in "?#%"):
        raise DominoError(f"Invalid file path {file_path!r}: '?', '#' and '%' are not allowed")
    return path


def _file_key(content: bytes) -> str:
    """The version key Domino reports for a DFS file: SHA-1 of its content."""
    return hashlib.sha1(content).hexdigest()


# (owner, name) lower-cased -> {"id": str, "git_based": bool | None}
_project_cache: Dict[tuple, Dict[str, Any]] = {}
_PROJECT_PAGE = 100
_PROJECT_MAX_PAGES = 500   # a hard stop against a server that never returns an empty page


def _project_info(user_name: str, project_name: str) -> Dict[str, Any]:
    """The id of project `user_name/project_name` and whether it is Git-based.

    Inside a Domino execution the platform's DOMINO_PROJECT_ID and DOMINO_IS_GIT_BASED are used
    when the names match the current project. Otherwise the Public API project list is searched
    page by page until an empty page (or totalCount is reached) and the result cached for the
    life of the process.
    """
    owner, name = user_name.strip(), project_name.strip()
    if not owner or not name:
        raise DominoError("user_name and project_name are required")
    key = (owner.lower(), name.lower())
    env_id = os.environ.get("DOMINO_PROJECT_ID")
    if env_id and os.environ.get("DOMINO_PROJECT_OWNER", "").lower() == key[0] \
            and os.environ.get("DOMINO_PROJECT_NAME", "").lower() == key[1]:
        git_based = _env_flag("DOMINO_IS_GIT_BASED")
        if git_based is None:
            project = (_api_json("GET", f"/api/projects/v1/projects/{env_id}") or {}).get("project") or {}
            git_based = bool(project.get("mainRepository"))
        return {"id": env_id, "git_based": git_based}
    cached = _project_cache.get(key)
    if cached:
        return cached
    offset = 0
    for _ in range(_PROJECT_MAX_PAGES):
        body = _api_json("GET", "/api/projects/beta/projects",
                         params={"offset": offset, "limit": _PROJECT_PAGE}) or {}
        projects = body.get("projects") or []
        if not projects:
            break
        for p in projects:
            if (p.get("ownerUsername", "").lower(), p.get("name", "").lower()) == key:
                info = {"id": p["id"], "git_based": bool(p.get("mainRepository"))}
                _project_cache[key] = info
                return info
        offset += len(projects)
        total = (body.get("metadata") or {}).get("totalCount")
        if isinstance(total, int) and offset >= total:
            break
    else:
        raise DominoError(f"Gave up looking for project {owner}/{name} after "
                          f"{_PROJECT_MAX_PAGES * _PROJECT_PAGE} projects.")
    raise DominoError(f"Project {owner}/{name} was not found among the projects this user can "
                      f"access. Check the owner user name and project name.")


def _resolve_project_id(user_name: str, project_name: str) -> str:
    return _project_info(user_name, project_name)["id"]


def _require_dfs_project(user_name: str, project_name: str) -> Dict[str, Any]:
    """The project info, or an error when the project is Git-based (file writes would be lost)."""
    info = _project_info(user_name, project_name)
    if info.get("git_based"):
        raise DominoError(f"{user_name}/{project_name} is a Git-based project: Jobs run the code in "
                          f"its Git repository, so a file uploaded through the Domino file API is not "
                          f"what a Job sees. Commit and push to the repository instead; the file tools "
                          f"are for DFS projects.")
    return info


def _latest_commit_id(project_id: str) -> str:
    body = _api_json("GET", f"/api/projects/beta/projects/{project_id}/commits/latest") or {}
    commit = body.get("commitId")
    if not commit:
        raise DominoError(f"Could not read the latest commit of project {project_id}")
    return commit


def _read_remote_file(project_id: str, commit_id: str, path: str) -> requests.Response:
    """GET the raw content of a project file at a commit (Public API); 403 and 404 are returned."""
    encoded = urllib.parse.quote(path, safe="")  # '/' must be sent as %2F
    return _api("GET", f"/api/projects/v1/projects/{project_id}/files/{commit_id}/{encoded}/content",
                allow=(403, 404))


def _listed_in_directory(user_name: str, project_name: str, path: str) -> bool:
    """Whether `path` appears in the listing of its parent directory (Internal API)."""
    parent = path.rsplit("/", 1)[0] if "/" in path else "/"
    # Domino Internal API, may change between Domino versions: no public listing route exists.
    files = _api_json("GET", "/v4/files/browseFiles",
                      params={"ownerUsername": user_name, "projectName": project_name, "filePath": parent})
    return any(f.get("path") == path for f in (files or []))


_MAX_FILE_BYTES = 2 * 1024 * 1024


def _decode_text(content: bytes, path: str) -> str:
    if len(content) > _MAX_FILE_BYTES:
        raise DominoError(f"{path} is {len(content)} bytes; this server reads files up to "
                          f"{_MAX_FILE_BYTES} bytes")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        raise DominoError(f"{path} is not UTF-8 text; this server only syncs text files") from None


def _remote_state(user_name: str, project_name: str, path: str, info: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """{"exists": bool, "commit_id": str, "content": str|None, "key": str|None} at the latest commit.

    "Does not exist" is concluded only from a 404, or from a 403 confirmed by a successful listing
    of the parent directory that does not contain the file (Domino answers 403 "... are not valid"
    for a missing path). Any other failure raises, so nothing is ever written over a file that
    could not be read.
    """
    project_id = (info or _project_info(user_name, project_name))["id"]
    commit_id = _latest_commit_id(project_id)
    resp = _read_remote_file(project_id, commit_id, path)
    if resp.status_code == 200:
        raw = resp.content
        return {"exists": True, "commit_id": commit_id, "content": _decode_text(raw, path), "key": _file_key(raw)}
    if resp.status_code == 403:
        if _listed_in_directory(user_name, project_name, path):
            raise DominoError(f"Could not read {path} in {user_name}/{project_name} although it exists "
                              f"({_describe_http_error('GET', 'file content', resp)}). Nothing was changed.")
    return {"exists": False, "commit_id": commit_id, "content": None, "key": None}


def _filter_domino_stdout(stdout_text: str) -> str:
    """
    Filters the stdout text from a Domino job run to extract the relevant output.
    It tries to extract text between known infrastructure markers, but falls back
    to returning the full stdout if markers aren't found.

    Note: Git and DFS projects have different paths:
    - Git projects: /mnt/artifacts/.domino/configure-spark-defaults.sh
    - DFS projects: /mnt/.domino/configure-spark-defaults.sh
    """
    start_patterns = [
        r"### Completed /mnt(?:/artifacts)?/\.domino/configure-spark-defaults\.sh ###",
        r"### Starting user code ###",
        r"Starting job\.\.\.",
    ]
    end_patterns = [
        r"Evaluating cleanup command on EXIT",
        r"### User code finished ###",
        r"Job completed",
    ]
    start_index = 0
    for pattern in start_patterns:
        match = re.search(pattern, stdout_text)
        if match:
            start_index = match.end()
            break
    end_index = len(stdout_text)
    for pattern in end_patterns:
        match = re.search(pattern, stdout_text[start_index:])
        if match:
            end_index = start_index + match.start()
            break
    filtered_text = stdout_text[start_index:end_index].strip()
    if not filtered_text:
        return stdout_text.strip() if stdout_text.strip() else "(No output captured)"
    return filtered_text


_MLFLOW_LOCAL_RUN = r"http://127\.0\.0\.1:8768/#/experiments/(\d+)/runs/([a-f0-9]+)"


def _mlflow_link(text: str, user_name: str, project_name: str) -> Dict[str, str] | None:
    """The Domino experiment-run path for a local MLflow URL printed by a job, if any.

    Returns {"mlflow_path": "/experiments/..."} plus "mlflow_url" when the user-facing host is known.
    """
    match = re.search(_MLFLOW_LOCAL_RUN, text)
    if not match:
        return None
    path = f"/experiments/{user_name}/{project_name}/{match.group(1)}/{match.group(2)}"
    result = {"mlflow_path": path}
    host = _get_external_host()
    if host:
        result["mlflow_url"] = f"{host}{path}"
    return result


# Both specs: "Will not retrieve over 10000 log lines at a time"; Domino Cloud 6.4 applied 1000 to a
# larger request. Ask for the maximum and follow the cursor until isComplete or the page cap.
_LOG_PAGE_LIMIT = 10000
_LOG_MAX_PAGES = 10


def _job_logs(job_id: str, log_type: str) -> Dict[str, Any]:
    """All lines of one log type for a job (Public API, paginated), capped at _LOG_MAX_PAGES."""
    lines: List[str] = []
    cursor = None
    is_complete = False
    last_entry: Dict[str, Any] | None = None
    for _ in range(_LOG_MAX_PAGES):
        params: Dict[str, Any] = {"logType": log_type, "limit": _LOG_PAGE_LIMIT}
        if cursor:
            params["latestTimeNano"] = cursor
        body = _api_json("GET", f"/api/jobs/beta/jobs/{job_id}/logs", params=params) or {}
        logs = body.get("logs") or {}
        entries = list(logs.get("logContent") or [])
        # The cursor means "from this time"; drop a boundary line repeated from the previous page.
        if entries and last_entry and entries[0].get("timestamp") == last_entry.get("timestamp") \
                and entries[0].get("log") == last_entry.get("log"):
            entries = entries[1:]
        lines.extend(str(e.get("log", "")) for e in entries)
        is_complete = bool(logs.get("isComplete"))
        next_cursor = ((body.get("metadata") or {}).get("pagination") or {}).get("latestTimeNano")
        if is_complete or not entries or not next_cursor or next_cursor == cursor:
            break
        last_entry = entries[-1]
        cursor = next_cursor
    return {"lines": lines, "is_complete": is_complete}


def _summarize_job(job: Dict[str, Any]) -> Dict[str, Any]:
    status = job.get("status") or {}
    return {
        "job_id": job.get("id"),
        "run_id": job.get("id"),  # a Domino job id and its run id are the same value
        "number": job.get("number"),
        "title": job.get("title"),
        "run_command": job.get("runCommand"),
        "status": status.get("executionStatus"),
        "is_completed": status.get("isCompleted"),
        "is_archived": status.get("isArchived"),
        "stage_times": job.get("stageTimes"),
        "commit_details": job.get("commitDetails"),
        "domino_stats": job.get("dominoStats"),
    }


# ---------------------------------------------------------------------------------------------
# Tools: jobs
# ---------------------------------------------------------------------------------------------

@mcp.tool()
@_threaded
def check_domino_job_run_results(run_id: str, user_name: str | None = None,
                                 project_name: str | None = None,
                                 log_type: str = "stdOut") -> Dict[str, Any]:
    """
    Returns the output of a Domino job run (its stdout by default).

    Args:
        run_id (str): The run id (= job id) of the job run to return the output of
        user_name (str, optional): The user name associated with the Domino Project. Kept for
            compatibility; the job id alone identifies the job.
        project_name (str, optional): The name of the Domino project. Kept for compatibility.
        log_type (str): Which log to return: "stdOut" (default), "stdErr", "prepareOutput" or
            "complete" (everything, interleaved).

    Returns:
        {"results": str, "line_count": int, "is_complete": bool, "mlflow_url"?: str}.
        is_complete is False when more log lines exist than this tool returns.
    """
    if log_type not in ("stdOut", "stdErr", "prepareOutput", "complete"):
        raise DominoError("log_type must be one of stdOut, stdErr, prepareOutput, complete")
    encoded_run_id = _validate_url_parameter(run_id, "run_id")
    logs = _job_logs(encoded_run_id, log_type)   # GET /api/jobs/beta/jobs/{jobId}/logs (Public API)
    raw = "\n".join(logs["lines"])

    text = _filter_domino_stdout(raw) if log_type == "stdOut" else (raw.strip() or "(No output captured)")
    result: Dict[str, Any] = {
        "results": text,
        "line_count": len(logs["lines"]),
        "is_complete": logs["is_complete"],
    }
    if user_name and project_name:
        link = _mlflow_link(text, user_name, project_name)
        if link:
            local_exp = r"View experiment at: http://127\.0\.0\.1:8768/#/experiments/\d+"
            kept = [ln for ln in text.splitlines()
                    if not re.search(_MLFLOW_LOCAL_RUN, ln) and not re.search(local_exp, ln)]
            result["results"] = "\n".join(kept).strip()
            result.update(link)
    if not logs["lines"]:
        result["note"] = ("No log lines were returned. The job may have produced no output of this "
                          "type, may still be starting, or its logs may have expired; try "
                          "log_type='complete'.")
    return result


@mcp.tool()
@_threaded
def check_domino_job_run_status(run_id: str, user_name: str | None = None,
                                project_name: str | None = None) -> Dict[str, Any]:
    """
    Checks the status of a job run to determine if it is finished, in progress or failed. A run can
    take a minute or more, so call this repeatedly until is_completed is true before reading
    results with check_domino_job_run_results.

    Args:
        run_id (str): The run id (= job id) of the job run to return the status of
        user_name (str, optional): Kept for compatibility; the job id alone identifies the job.
        project_name (str, optional): Kept for compatibility.

    Returns:
        {"job_id", "run_id", "number", "title", "run_command", "status", "is_completed", ...}.
        status is Domino's executionStatus, for example Queued, Preparing, Running, Succeeded,
        Failed, Stopped.
    """
    encoded_run_id = _validate_url_parameter(run_id, "run_id")
    body = _api_json("GET", f"/api/jobs/beta/jobs/{encoded_run_id}") or {}   # Public API
    return _summarize_job(body.get("job") or {})


@mcp.tool()
@_threaded
def run_domino_job(user_name: str, project_name: str, run_command: str, title: str,
                   git_branch: str | None = None) -> Dict[str, Any]:
    """
    Runs a command as a Job on the Domino platform, typically a script such as
    'python my_script.py --arg1 val1'. The command runs against the project's latest files: for a
    DFS project the synced files; for a Git-based project the repository's default branch
    (pushed commits only) unless git_branch names another branch.

    Args:
        user_name (str): The user name of the project owner.
        project_name (str): The name of the Domino project.
        run_command (str): The command to run, as one string, exactly as you would type it in a
            shell. Example: 'python my_script.py --arg1 val1 --name "my run"'
        title (str): A title that helps identify the job later. Example: 'running training.py'
        git_branch (str, optional): For a Git-based project, the branch to run from instead of
            the default branch.

    Returns:
        {"job_id", "run_id", "number", "status", ...} of the new job. Poll
        check_domino_job_run_status with run_id until is_completed is true.
    """
    if not run_command or not run_command.strip():
        raise DominoError("run_command must not be empty")
    project_id = _resolve_project_id(user_name, project_name)
    payload: Dict[str, Any] = {"projectId": project_id, "runCommand": run_command.strip(), "title": title}
    if git_branch:
        payload["mainRepoGitRef"] = {"refType": "branches", "value": git_branch}
    body = _api_json("POST", "/api/jobs/v1/jobs", json=payload) or {}   # Public API (NewJobV1)
    result = _summarize_job(body.get("job") or {})
    result["message"] = (f"Started job {result.get('number')} ({result.get('job_id')}) in "
                         f"{user_name}/{project_name}. Poll check_domino_job_run_status with "
                         f"run_id until is_completed is true, then read "
                         f"check_domino_job_run_results.")
    return result


@mcp.tool()
def open_web_browser(url: str) -> bool:
    """Opens the specified URL in the default web browser on the machine running this server.
    Inside a Domino Workspace or Job there is no browser: the tool returns False without doing
    anything, and you should show the URL to the user instead.

    Args:
        url: The URL to open.

    Returns:
        True if the browser was opened successfully, False otherwise.
    """
    if _is_domino_workspace() or not url.startswith(("http://", "https://")):
        return False
    try:
        return bool(webbrowser.open_new_tab(url))
    except webbrowser.Error:
        return False


@mcp.tool()
async def get_domino_environment_info() -> Dict[str, Any]:
    """
    Returns information about the current Domino environment. Call this at the start of a
    session to learn whether the server runs inside a Domino execution, the project owner and
    name, whether the project is Git-based or DFS, and which authentication is in use.

    Inside a Domino Workspace or Job everything comes from platform environment variables.
    Outside Domino the response says what is configured (DOMINO_HOST, DOMINO_TOKEN) and what
    is missing; project owner, project name and the DFS setting then come from the user or
    from domino_project_settings.md.
    """
    inside = _is_domino_workspace()
    info: Dict[str, Any] = {
        "inside_domino_workspace": inside,
        "auth_mode": _auth_mode(),
        "domino_host": None,
    }
    try:
        info["domino_host"] = _get_domino_host()
    except DominoError as e:
        info["error"] = str(e)

    if inside:
        info["user_name"] = os.environ.get("DOMINO_PROJECT_OWNER", "")
        info["project_name"] = os.environ.get("DOMINO_PROJECT_NAME", "")
        info["project_id"] = os.environ.get("DOMINO_PROJECT_ID", "")
        info["run_id"] = os.environ.get("DOMINO_RUN_ID", "")
        info["working_dir"] = os.environ.get("DOMINO_WORKING_DIR", "")
        is_git = _env_flag("DOMINO_IS_GIT_BASED")
        if is_git is None:
            is_git = _probe_git(info["working_dir"])
        info["is_git_based"] = is_git
        info["is_dfs_project"] = (not is_git) if is_git is not None else None
        if is_git is None:
            info["note"] = ("DOMINO_IS_GIT_BASED is not set and the working directory could not be "
                            "probed; ask the user whether the project is Git-based or DFS.")
    else:
        info["is_git_based"] = None
        info["is_dfs_project"] = None
        if info["auth_mode"] == "none":
            info["error"] = info.get("error") or ("DOMINO_TOKEN is not set. " + _auth_help())
        elif info["auth_mode"] == "invalid_token":
            try:
                _get_token()
            except DominoError as e:
                info["error"] = str(e)
        if os.environ.get("DOMINO_API_KEY"):
            info["warning"] = ("DOMINO_API_KEY is set but legacy API keys are not supported by this "
                               "server; set DOMINO_TOKEN instead.")
        info["note"] = ("Running outside Domino. Take the project owner, project name and the "
                        "DFS setting from the user or from domino_project_settings.md.")
    return info


def _probe_git(working_dir: str) -> bool | None:
    """Fallback when DOMINO_IS_GIT_BASED is unset: is DOMINO_WORKING_DIR inside a Git work tree?"""
    if not working_dir or not os.path.isdir(working_dir):
        return None
    import subprocess
    try:
        result = subprocess.run(["git", "-C", working_dir, "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    return result.returncode == 0 and result.stdout.strip() == "true"


# ---------------------------------------------------------------------------------------------
# Tools: DFS (Domino File System) files
# These support syncing files with non-Git Domino projects. Reads use the Public API; listing
# uses the Domino Internal API and uploading the legacy v1 API (no public equivalent exists).
# Writes refuse Git-based projects, whose Jobs run the repository, not uploaded files.
# ---------------------------------------------------------------------------------------------

# Versions this process has seen, for conflict detection in smart_sync_file.
# Key: (user_name, project_name, file_path) -> {"key": sha1, "content": str}
_file_version_cache: Dict[tuple, Dict[str, Any]] = {}


@mcp.tool()
@_threaded
def list_domino_project_files(user_name: str, project_name: str, path: str = "/") -> Dict[str, Any]:
    """
    Lists the files and subdirectories in one directory of a Domino project (not recursive).
    Works with DFS (non-git) projects. Use it to see what exists before uploading or downloading.

    Args:
        user_name (str): The username of the project owner (e.g., 'etan_lightstone')
        project_name (str): The name of the Domino project (e.g., 'diabetes_dfs_proj')
        path (str): The directory to list (default: "/" for the project root). Files in
            subdirectories are not included; list each subdirectory separately.

    Returns:
        {"path", "files": [{path, name, size, lastModified, key}], "directories": [{path, name}],
         "count"}
    """
    directory = path.strip() or "/"
    params = {"ownerUsername": user_name, "projectName": project_name, "filePath": directory}
    # Domino Internal API, may change between Domino versions: the Public API has no directory
    # listing for DFS project files.
    files = _api_json("GET", "/v4/files/browseFiles", params=params) or []
    dirs = _api_json("GET", "/v4/files/browseDirectories", params=params) or []
    simplified_files = [{
        "path": f.get("path"),
        "name": f.get("name"),
        "size": f.get("size"),
        "lastModified": f.get("lastModified"),
        "key": f.get("key"),
    } for f in files]
    simplified_dirs = [{"path": d.get("path"), "name": d.get("name")} for d in dirs]
    return {
        "path": directory,
        "files": simplified_files,
        "directories": simplified_dirs,
        "count": len(simplified_files),
    }


def _upload(user_name: str, project_name: str, path: str, content: str) -> Dict[str, Any]:
    encoded_user_name = _validate_url_parameter(user_name, "user_name")
    encoded_project_name = _validate_url_parameter(project_name, "project_name")
    encoded_path = "/".join(urllib.parse.quote(seg, safe="") for seg in path.split("/"))
    data = content.encode("utf-8")
    # Legacy v1 API, not in any published spec: the Public API has no upload route for DFS
    # project files.
    resp = _api("PUT", f"/v1/projects/{encoded_user_name}/{encoded_project_name}/{encoded_path}",
                data=data, headers={"Content-Type": "application/octet-stream"})
    try:
        body = resp.json()
    except ValueError:
        body = {}
    return {
        "success": True,
        "path": body.get("path") or path,
        "size": body.get("size", len(data)),
        "key": _file_key(data),   # always the local SHA-1, the same source the conflict check uses
        "lastModified": body.get("lastModified"),
    }


def _upload_file(user_name: str, project_name: str, file_path: str, file_content: str,
                 overwrite: bool) -> Dict[str, Any]:
    path = _normalize_project_path(file_path)
    info = _require_dfs_project(user_name, project_name)
    if not overwrite:
        remote = _remote_state(user_name, project_name, path, info)
        if remote["exists"]:
            if remote["content"] == file_content:
                return {"success": True, "action": "no_change", "path": path, "key": remote["key"],
                        "message": "File content identical to remote, no upload needed"}
            raise DominoError(f"{path} already exists in {user_name}/{project_name} with different "
                              f"content (key {remote['key']}). Use smart_sync_file to compare and "
                              f"merge, or pass overwrite=True to replace it.")
    result = _upload(user_name, project_name, path, file_content)
    _file_version_cache[(user_name, project_name, path)] = {"key": result["key"], "content": file_content}
    return result


@mcp.tool()
@_threaded
def upload_file_to_domino_project(
    user_name: str,
    project_name: str,
    file_path: str,
    file_content: str,
    overwrite: bool = False
) -> Dict[str, Any]:
    """
    Uploads a text file to a DFS (non-git) Domino project. Creates the file if it does not exist.
    Refuses to replace an existing file unless overwrite=True; prefer smart_sync_file, which
    detects conflicts instead of overwriting. Refuses Git-based projects (commit and push there).

    Args:
        user_name (str): The username of the project owner (e.g., 'etan_lightstone')
        project_name (str): The name of the Domino project (e.g., 'diabetes_dfs_proj')
        file_path (str): The path where the file should be saved in the project (e.g., 'scripts/train.py')
        file_content (str): The content of the file to upload
        overwrite (bool): Replace the file if it already exists (default False).

    Returns:
        {"success": True, "path", "size", "key", "lastModified"} on success.
    """
    return _upload_file(user_name, project_name, file_path, file_content, overwrite)


@mcp.tool()
@_threaded
def download_file_from_domino_project(
    user_name: str,
    project_name: str,
    file_path: str
) -> Dict[str, Any]:
    """
    Downloads a text file's content from a Domino project at its latest commit. Works with DFS
    (non-git) projects.

    IMPORTANT: This function remembers the version you downloaded. When you later use
    smart_sync_file to upload changes, it detects whether someone else modified the file in
    the meantime.

    Args:
        user_name (str): The username of the project owner (e.g., 'etan_lightstone')
        project_name (str): The name of the Domino project (e.g., 'diabetes_dfs_proj')
        file_path (str): The path of the file to download (e.g., 'scripts/train.py')

    Returns:
        {"success": True, "path", "content", "key", "commitId"}; key is the version identifier
        used for conflict detection.
    """
    path = _normalize_project_path(file_path)
    remote = _remote_state(user_name, project_name, path)   # Public API
    if not remote["exists"]:
        raise DominoError(f"{path} does not exist in {user_name}/{project_name} at commit "
                          f"{remote['commit_id']}. Use list_domino_project_files to see what exists.")
    _file_version_cache[(user_name, project_name, path)] = {"key": remote["key"], "content": remote["content"]}
    return {
        "success": True,
        "path": path,
        "content": remote["content"],
        "key": remote["key"],
        "commitId": remote["commit_id"],
    }


@mcp.tool()
@_threaded
def sync_local_file_to_domino(
    user_name: str,
    project_name: str,
    local_file_path: str,
    domino_file_path: str | None = None,
    overwrite: bool = False
) -> Dict[str, Any]:
    """
    Reads a local text file and uploads it to a DFS (non-git) Domino project. Refuses to replace
    an existing remote file unless overwrite=True; use smart_sync_file for conflict detection.
    Refuses Git-based projects (commit and push there).

    Args:
        user_name (str): The username of the project owner (e.g., 'etan_lightstone')
        project_name (str): The name of the Domino project (e.g., 'diabetes_dfs_proj')
        local_file_path (str): The absolute path to the local file to upload
        domino_file_path (str, optional): The path in Domino where the file should be saved.
                                          If not provided, uses the filename from local_file_path.
        overwrite (bool): Replace the remote file if it already exists (default False).

    Returns:
        Upload result on success.
    """
    try:
        with open(local_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        raise DominoError(f"Local file not found: {local_file_path}") from None
    except UnicodeDecodeError:
        raise DominoError(f"{local_file_path} is not UTF-8 text; this server only syncs text files") from None
    except OSError as e:
        raise DominoError(f"Failed to read local file: {e}") from None

    if domino_file_path is None:
        domino_file_path = os.path.basename(local_file_path)

    return _upload_file(user_name, project_name, domino_file_path, content, overwrite)


@mcp.tool()
@_threaded
def smart_sync_file(
    user_name: str,
    project_name: str,
    file_path: str,
    content: str,
    force_overwrite: bool = False
) -> Dict[str, Any]:
    """
    Syncs a text file to a DFS (non-git) Domino project with conflict detection. Refuses
    Git-based projects (commit and push there).

    This is the RECOMMENDED way to upload files when working with shared projects. It never
    replaces a remote file it has not seen: it compares the remote version with the one you
    downloaded (or uploaded) earlier and reports a conflict instead of overwriting.

    Workflow:
    1. If the file does not exist remotely, it is created.
    2. If it exists and you have not downloaded it in this session, the remote content is
       returned as a conflict (unless it is identical to yours).
    3. If you downloaded it earlier and the remote version is unchanged, your content is uploaded.
    4. If the remote version changed since your download, both versions are returned as a conflict.
    Only force_overwrite=True replaces a conflicting remote file.

    Args:
        user_name (str): The username of the project owner
        project_name (str): The name of the Domino project
        file_path (str): The path where the file should be saved
        content (str): The new content to upload
        force_overwrite (bool): Replace the remote file whatever its current content.

    Returns:
        On success: {"success": True, "action": "created"|"uploaded"|"no_change"|"force_overwritten", "key"}
        On conflict: {"conflict": True, "message", "remote_content", "remote_key", "your_base_key"?,
                      "original_content"?, "suggestion"}
    """
    path = _normalize_project_path(file_path)
    cache_key = (user_name, project_name, path)
    cached = _file_version_cache.get(cache_key)
    info = _require_dfs_project(user_name, project_name)
    remote = _remote_state(user_name, project_name, path, info)   # Public API, latest commit

    def _do_upload(action: str, **extra: Any) -> Dict[str, Any]:
        result = _upload(user_name, project_name, path, content)
        _file_version_cache[cache_key] = {"key": result["key"], "content": content}
        return {"success": True, "action": action, "path": path, "key": result["key"],
                "size": result["size"], "message": f"{action}: {path}", **extra}

    # Case 1: the file does not exist remotely: create it.
    if not remote["exists"]:
        return _do_upload("created")

    # Identical content needs no upload, whatever the history.
    if remote["content"] == content:
        _file_version_cache[cache_key] = {"key": remote["key"], "content": content}
        return {"success": True, "action": "no_change", "path": path, "key": remote["key"],
                "message": "File content identical to remote, no upload needed"}

    if force_overwrite:
        return _do_upload("force_overwritten", previous_remote_key=remote["key"])

    # Case 2: the file exists but this session has no baseline for it.
    if cached is None:
        return {
            "conflict": True,
            "message": (f"'{path}' already exists in {user_name}/{project_name} with different "
                        f"content and you have not downloaded it in this session. Nothing was "
                        f"uploaded."),
            "remote_content": remote["content"],
            "remote_key": remote["key"],
            "suggestion": ("Review remote_content, merge it with your version if needed, then call "
                           "smart_sync_file again with force_overwrite=True to upload your final "
                           "version (or download_file_from_domino_project first to set a baseline)."),
        }

    # Case 3: a baseline exists; did the remote file change since then?
    if remote["key"] != cached["key"]:
        return {
            "conflict": True,
            "message": f"Remote file '{path}' changed since you last downloaded it. Nothing was uploaded.",
            "your_base_key": cached["key"],
            "remote_key": remote["key"],
            "remote_content": remote["content"],
            "original_content": cached.get("content", ""),
            "suggestion": ("Someone modified this file. Review the remote changes, merge if needed, "
                           "then call smart_sync_file again with force_overwrite=True."),
        }

    # Case 4: remote unchanged since the baseline: safe to upload.
    return _do_upload("uploaded")


if __name__ == "__main__":
    # Initialize and run the server using stdio transport
    mcp.run(transport='stdio')
