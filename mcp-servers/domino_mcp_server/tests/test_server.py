"""Unit tests for domino_mcp_server with mocked HTTP. Run: uv run --with pytest pytest"""
import hashlib
import os
from pathlib import Path

import pytest

from conftest import FakeResponse, import_server

OWNER, PROJECT, PID = "alice", "demo", "0123456789abcdef01234567"
COMMIT = "fb2876cc5381e72ec8213596d80fef2d80de60e6"
GIT_REPO = {"id": "r1", "name": "demo", "serviceProvider": "github", "uri": "git@github.com:alice/demo.git"}


def _add_project_lookup(http, projects=None):
    projects = projects if projects is not None else [
        {"id": "ffffffffffffffffffffffff", "name": "other", "ownerUsername": OWNER},
        {"id": PID, "name": PROJECT, "ownerUsername": OWNER},
    ]
    http.add("GET", "/api/projects/beta/projects", FakeResponse(200, {"projects": projects, "metadata": {}}))


def _add_listing(http, entries):
    """browseFiles answers with `entries` (list of paths) for any directory."""
    http.add("GET", "/v4/files/browseFiles",
             FakeResponse(200, [{"path": p, "name": p.rsplit("/", 1)[-1], "size": 1, "lastModified": 1, "key": "k", "goalIds": []} for p in entries]))


def _add_file(http, path, content: bytes | None, commit=COMMIT, missing_status=403, listing=()):
    http.add("GET", f"/api/projects/beta/projects/{PID}/commits/latest",
             FakeResponse(200, {"commitId": commit, "metadata": {}}))
    encoded = path.replace("/", "%2F")
    route = f"/api/projects/v1/projects/{PID}/files/{commit}/{encoded}/content"
    if content is None:
        body = {"errors": [f"Not authorized: File {path}, commitId AnyObjectId[{commit}], projectId: {PID} are not valid."]} \
            if missing_status == 403 else {"errors": ["not found"]}
        http.add("GET", route, FakeResponse(missing_status, body))
        _add_listing(http, listing)
    else:
        http.add("GET", route, FakeResponse(200, content=content))


def _add_upload(http, path):
    def handler(kwargs):
        data = kwargs["data"]
        return FakeResponse(200, {"path": path, "size": len(data), "key": "server-key", "lastModified": 1})
    http.add("PUT", f"/v1/projects/{OWNER}/{PROJECT}/{path}", handler)


def _puts(http):
    return [c for c in http.calls if c[0] == "PUT"]


# ---------------------------------------------------------------------------------------------
# Auth and host selection
# ---------------------------------------------------------------------------------------------

def test_inside_domino_uses_proxy_without_auth_header(server, clean_env):
    clean_env.setenv("DOMINO_API_PROXY", "http://localhost:8899/")
    clean_env.setenv("DOMINO_API_HOST", "http://nucleus-frontend.domino-platform:80")
    clean_env.setenv("DOMINO_TOKEN", "ignored-inside-domino")
    assert server._is_domino_workspace()
    assert server._get_domino_host() == "http://localhost:8899"
    assert server._get_auth_headers() == {}
    assert server._auth_mode() == "api_proxy"


def test_outside_domino_sends_bearer_token(server, clean_env, http):
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com/")
    clean_env.setenv("DOMINO_TOKEN", "pat-value")
    assert not server._is_domino_workspace()
    assert server._get_domino_host() == "https://domino.example.com"
    assert server._get_auth_headers() == {"Authorization": "Bearer pat-value"}
    http.add("GET", "/api/users/v1/self", FakeResponse(200, {"user": {"userName": "alice"}}))
    server._api("GET", "/api/users/v1/self")
    method, path, kwargs = http.calls[-1]
    assert kwargs["base"] == "https://domino.example.com"
    assert kwargs["headers"] == {"Authorization": "Bearer pat-value"}
    assert "X-Domino-Api-Key" not in kwargs["headers"]
    assert kwargs["timeout"] == server._TIMEOUT


def test_outside_domino_accepts_domino_api_host_as_fallback(server, clean_env):
    clean_env.setenv("DOMINO_API_HOST", "https://domino.example.com")
    clean_env.setenv("DOMINO_TOKEN", "t")
    assert server._get_domino_host() == "https://domino.example.com"


def test_outside_domino_missing_config_gives_clear_error_naming_the_env_file(server, clean_env, tmp_path):
    with pytest.raises(server.DominoError) as host_err:
        server._get_domino_host()
    text = str(host_err.value)
    assert "DOMINO_HOST" in text and "DOMINO_TOKEN" in text
    assert str(tmp_path / "absent.env") in text            # Codex users can only use the env file
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com")
    with pytest.raises(server.DominoError) as token_err:
        server._get_auth_headers()
    assert "DOMINO_TOKEN is not set" in str(token_err.value)
    assert "Personal Access Token" in str(token_err.value)


def test_legacy_api_key_is_rejected_with_migration_message(server, clean_env):
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com")
    clean_env.setenv("DOMINO_API_KEY", "OLDKEYVALUE-123")
    with pytest.raises(server.DominoError) as err:
        server._get_auth_headers()
    assert "deprecated" in str(err.value) and "DOMINO_TOKEN" in str(err.value)
    assert "OLDKEYVALUE-123" not in str(err.value)


def test_literal_placeholders_and_empty_values_are_treated_as_unset(clean_env):
    clean_env.setenv("DOMINO_HOST", "${DOMINO_HOST}")
    clean_env.setenv("DOMINO_TOKEN", "${env:DOMINO_TOKEN}")
    clean_env.setenv("DOMINO_API_KEY", "")
    module = import_server()
    assert "DOMINO_HOST" not in os.environ and "DOMINO_TOKEN" not in os.environ
    assert "DOMINO_API_KEY" not in os.environ
    with pytest.raises(module.DominoError):
        module._get_domino_host()


def test_env_file_fills_missing_or_empty_variables_but_never_overrides(clean_env, tmp_path):
    env_file = tmp_path / "mcp.env"
    env_file.write_text("DOMINO_HOST=https://from-file.example.com\nDOMINO_TOKEN=file-token\n")
    clean_env.setenv("DOMINO_MCP_ENV_FILE", str(env_file))
    clean_env.setenv("DOMINO_TOKEN", "shell-token")
    clean_env.setenv("DOMINO_HOST", "")                      # empty, as a host might pass it
    module = import_server()
    assert module._get_domino_host() == "https://from-file.example.com"
    assert module._get_auth_headers() == {"Authorization": "Bearer shell-token"}


def test_default_env_file_location(server, clean_env, tmp_path):
    clean_env.delenv("DOMINO_MCP_ENV_FILE")
    clean_env.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert server._env_file_path() == tmp_path / "domino-mcp-server" / ".env"


def test_http_host_is_refused_unless_loopback_or_opted_in(server, clean_env):
    clean_env.setenv("DOMINO_TOKEN", "t")
    clean_env.setenv("DOMINO_HOST", "http://domino.example.com")
    with pytest.raises(server.DominoError) as err:
        server._get_domino_host()
    assert "clear text" in str(err.value) and "DOMINO_INSECURE_HTTP" in str(err.value)
    clean_env.setenv("DOMINO_HOST", "http://localhost:8080")
    assert server._get_domino_host() == "http://localhost:8080"
    clean_env.setenv("DOMINO_HOST", "http://domino.example.com")
    clean_env.setenv("DOMINO_INSECURE_HTTP", "true")
    assert server._get_domino_host() == "http://domino.example.com"
    clean_env.setenv("DOMINO_HOST", "domino.example.com")
    with pytest.raises(server.DominoError):
        server._get_domino_host()


def test_http_error_outside_domino_mentions_token(server, clean_env, http):
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com")
    clean_env.setenv("DOMINO_TOKEN", "t")
    http.add("GET", "/api/jobs/beta/jobs/abc", FakeResponse(401, {"message": "Unauthorized"}))
    with pytest.raises(server.DominoError) as err:
        server._api("GET", "/api/jobs/beta/jobs/abc")
    assert "HTTP 401" in str(err.value) and "DOMINO_TOKEN" in str(err.value)


def test_non_json_success_body_points_at_domino_host(server, clean_env, http):
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com")
    clean_env.setenv("DOMINO_TOKEN", "t")
    http.add("GET", "/api/users/v1/self", FakeResponse(200, content=b"<!doctype html><html>login</html>"))
    with pytest.raises(server.DominoError) as err:
        server._api_json("GET", "/api/users/v1/self")
    assert "non-JSON" in str(err.value) and "DOMINO_HOST" in str(err.value)


# ---------------------------------------------------------------------------------------------
# Token hygiene: never echo the token
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["SECRETPAT123\r", "SECRETPAT123\n", "  SECRETPAT123 \r\n", "\tSECRETPAT123"])
def test_token_is_stripped_of_surrounding_whitespace(server, clean_env, raw):
    clean_env.setenv("DOMINO_TOKEN", raw)
    assert server._get_auth_headers() == {"Authorization": "Bearer SECRETPAT123"}
    assert server._auth_mode() == "bearer_token"


@pytest.mark.parametrize("raw", ["SECRET PAT123", "SECRET\rPAT123", "SECRET\nPAT", "SECRET\x7fPAT", "SECRET\x01PAT"])
def test_token_with_inner_whitespace_or_control_chars_is_rejected_without_echo(server, clean_env, raw, run):
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com")
    clean_env.setenv("DOMINO_TOKEN", raw)
    with pytest.raises(server.DominoError) as err:
        server._get_auth_headers()
    assert "DOMINO_TOKEN" in str(err.value) and "SECRET" not in str(err.value)
    info = run(server.get_domino_environment_info())
    assert info["auth_mode"] == "invalid_token" and "SECRET" not in info["error"]


def test_request_exception_text_is_redacted(server, clean_env, http):
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com")
    clean_env.setenv("DOMINO_TOKEN", "SECRETPAT123")

    def boom(kwargs):
        raise server.requests.exceptions.InvalidHeader(
            f"Invalid header value: {kwargs['headers']['Authorization']!r} for SECRETPAT123")
    http.add("GET", "/api/users/v1/self", boom)
    with pytest.raises(server.DominoError) as err:
        server._api("GET", "/api/users/v1/self")
    text = str(err.value)
    assert "SECRETPAT123" not in text and "<redacted>" in text and "failed" in text


def test_http_error_body_is_redacted(server, clean_env, http):
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com")
    clean_env.setenv("DOMINO_TOKEN", "SECRETPAT123")
    http.add("GET", "/api/users/v1/self",
             FakeResponse(401, {"message": "bad token SECRETPAT123 in header Bearer SECRETPAT123"}))
    with pytest.raises(server.DominoError) as err:
        server._api("GET", "/api/users/v1/self")
    assert "SECRETPAT123" not in str(err.value)
    http.add("GET", "/api/users/v1/self", FakeResponse(500, content=b"oops SECRETPAT123", text="oops SECRETPAT123"))
    with pytest.raises(server.DominoError) as err:
        server._api("GET", "/api/users/v1/self")
    assert "SECRETPAT123" not in str(err.value)


def test_environment_info_never_contains_the_token(server, clean_env, run):
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com")
    clean_env.setenv("DOMINO_TOKEN", "SECRETPAT123")
    assert "SECRETPAT123" not in str(run(server.get_domino_environment_info()))


# ---------------------------------------------------------------------------------------------
# Environment recovery from an ancestor process (Codex strips the environment)
# ---------------------------------------------------------------------------------------------

def _fake_proc(tmp_path, chain):
    """chain: list of (pid, ppid, env dict) from the server's parent upwards."""
    proc = tmp_path / "proc"
    for pid, ppid, env in chain:
        d = proc / str(pid)
        d.mkdir(parents=True)
        (d / "environ").write_bytes(b"\0".join(f"{k}={v}".encode() for k, v in env.items()) + b"\0")
        (d / "stat").write_text(f"{pid} (node (main)) S {ppid} 1 1 0 -1")
    return str(proc)


def test_recovers_domino_vars_from_nearest_ancestor(server, tmp_path):
    proc = _fake_proc(tmp_path, [
        (300, 200, {"HOME": "/home/u", "PATH": "/bin"}),                      # codex, stripped
        (200, 100, {"DOMINO_API_PROXY": "http://localhost:8899", "DOMINO_API_HOST": "http://api",
                    "DOMINO_PROJECT_OWNER": "alice", "DOMINO_PROJECT_NAME": "demo",
                    "DOMINO_PROJECT_ID": PID, "DOMINO_IS_GIT_BASED": "false",
                    "DOMINO_WORKING_DIR": "/mnt", "DOMINO_USER_API_KEY": "secret",
                    "DOMINO_RUN_ID": "run1"}),
    ])
    env = {"HOME": "/home/u", "DOMINO_PROJECT_NAME": "preset"}
    recovered = server._recover_domino_env(env, proc=proc, start_pid=300)
    assert set(recovered) == {"DOMINO_API_HOST", "DOMINO_API_PROXY", "DOMINO_PROJECT_ID",
                              "DOMINO_PROJECT_OWNER", "DOMINO_IS_GIT_BASED", "DOMINO_WORKING_DIR",
                              "DOMINO_RUN_ID"}
    assert env["DOMINO_API_PROXY"] == "http://localhost:8899"
    assert env["DOMINO_IS_GIT_BASED"] == "false" and env["DOMINO_WORKING_DIR"] == "/mnt"
    assert env["DOMINO_PROJECT_NAME"] == "preset"          # existing values are kept
    assert "DOMINO_USER_API_KEY" not in env                 # only the listed names are copied


def test_recovery_is_a_no_op_when_already_set_or_without_procfs(server, tmp_path):
    proc = _fake_proc(tmp_path, [(300, 1, {"DOMINO_API_PROXY": "http://localhost:8899"})])
    env = {"DOMINO_API_PROXY": "http://set"}
    assert server._recover_domino_env(env, proc=proc, start_pid=300) == []
    assert env == {"DOMINO_API_PROXY": "http://set"}
    env = {}
    assert server._recover_domino_env(env, proc=str(tmp_path / "no-proc"), start_pid=300) == []
    assert env == {}


def test_recovery_stops_at_depth_or_pid_1(server, tmp_path):
    proc = _fake_proc(tmp_path, [(300, 1, {"HOME": "/home/u"})])
    env = {}
    assert server._recover_domino_env(env, proc=proc, start_pid=300) == []


def test_import_is_hermetic_under_the_test_fixture(server):
    """The fixture pins os.getppid to 1, so import-time recovery cannot read the real /proc."""
    assert "DOMINO_API_PROXY" not in os.environ and not server._is_domino_workspace()


# ---------------------------------------------------------------------------------------------
# get_domino_environment_info: DFS detection from DOMINO_IS_GIT_BASED, not from `git status`
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("flag, expected_git, expected_dfs", [
    ("true", True, False), ("True", True, False), ("false", False, True), ("FALSE", False, True),
])
def test_environment_info_inside_domino(server, clean_env, run, flag, expected_git, expected_dfs):
    clean_env.setenv("DOMINO_API_PROXY", "http://localhost:8899")
    clean_env.setenv("DOMINO_PROJECT_OWNER", OWNER)
    clean_env.setenv("DOMINO_PROJECT_NAME", PROJECT)
    clean_env.setenv("DOMINO_PROJECT_ID", PID)
    clean_env.setenv("DOMINO_IS_GIT_BASED", flag)
    clean_env.setenv("DOMINO_WORKING_DIR", "/mnt/code")
    info = run(server.get_domino_environment_info())
    assert info["inside_domino_workspace"] is True
    assert info["auth_mode"] == "api_proxy"
    assert info["domino_host"] == "http://localhost:8899"
    assert info["user_name"] == OWNER and info["project_name"] == PROJECT and info["project_id"] == PID
    assert info["is_git_based"] is expected_git and info["is_dfs_project"] is expected_dfs
    assert info["working_dir"] == "/mnt/code"
    assert "error" not in info


def test_environment_info_inside_domino_without_flag_probes_working_dir(server, clean_env, run, tmp_path, monkeypatch):
    clean_env.setenv("DOMINO_API_PROXY", "http://localhost:8899")
    clean_env.setenv("DOMINO_WORKING_DIR", str(tmp_path))
    calls = []

    class Result:
        returncode, stdout = 0, "true\n"

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Result()
    monkeypatch.setattr("subprocess.run", fake_run)
    info = run(server.get_domino_environment_info())
    assert info["is_git_based"] is True and info["is_dfs_project"] is False
    assert calls and calls[0][:3] == ["git", "-C", str(tmp_path)]   # probes the project, not the server's cwd


def test_environment_info_outside_domino_reports_missing_config(server, clean_env, run):
    info = run(server.get_domino_environment_info())
    assert info["inside_domino_workspace"] is False
    assert info["auth_mode"] == "none"
    assert info["domino_host"] is None
    assert "DOMINO_HOST" in info["error"] and "DOMINO_TOKEN" in info["error"]
    assert info["is_dfs_project"] is None


def test_environment_info_outside_domino_with_token(server, clean_env, run):
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com")
    clean_env.setenv("DOMINO_TOKEN", "t")
    clean_env.setenv("DOMINO_API_KEY", "legacy")
    info = run(server.get_domino_environment_info())
    assert info["auth_mode"] == "bearer_token" and info["domino_host"] == "https://domino.example.com"
    assert "error" not in info and "DOMINO_TOKEN" in info["warning"]


def test_open_web_browser_is_a_no_op_inside_domino(server, clean_env, monkeypatch):
    opened = []
    monkeypatch.setattr(server.webbrowser, "open_new_tab", lambda url: opened.append(url) or True)
    clean_env.setenv("DOMINO_API_PROXY", "http://localhost:8899")
    assert server.open_web_browser("https://example.com/x") is False and opened == []
    clean_env.delenv("DOMINO_API_PROXY")
    assert server.open_web_browser("https://example.com/x") is True and opened == ["https://example.com/x"]
    assert server.open_web_browser("file:///etc/passwd") is False


# ---------------------------------------------------------------------------------------------
# Jobs on the Public API
# ---------------------------------------------------------------------------------------------

@pytest.fixture
def laptop(clean_env):
    clean_env.setenv("DOMINO_HOST", "https://domino.example.com")
    clean_env.setenv("DOMINO_TOKEN", "t")
    return clean_env


def test_run_domino_job_posts_public_api_body(server, laptop, http, run):
    _add_project_lookup(http)
    http.add("POST", "/api/jobs/v1/jobs", FakeResponse(200, {"job": {
        "id": "job1", "number": 7, "runCommand": "python train.py --name \"my run\"", "title": "t",
        "status": {"executionStatus": "Queued", "isCompleted": False, "isArchived": False}}}))
    result = run(server.run_domino_job(OWNER, PROJECT, 'python train.py --name "my run"', "t"))
    method, path, kwargs = http.calls[-1]
    assert (method, path) == ("POST", "/api/jobs/v1/jobs")
    assert kwargs["json"] == {"projectId": PID, "runCommand": 'python train.py --name "my run"', "title": "t"}
    assert result["job_id"] == "job1" and result["run_id"] == "job1" and result["status"] == "Queued"
    # project lookup is cached for the process
    run(server.run_domino_job(OWNER, PROJECT, "python x.py", "t2", git_branch="feature/x"))
    assert sum(1 for m, p, _ in http.calls if p == "/api/projects/beta/projects") == 1
    assert http.calls[-1][2]["json"]["mainRepoGitRef"] == {"refType": "branches", "value": "feature/x"}


def test_run_domino_job_inside_domino_uses_platform_project_id(server, clean_env, http, run):
    clean_env.setenv("DOMINO_API_PROXY", "http://localhost:8899")
    clean_env.setenv("DOMINO_PROJECT_OWNER", OWNER)
    clean_env.setenv("DOMINO_PROJECT_NAME", PROJECT)
    clean_env.setenv("DOMINO_PROJECT_ID", PID)
    clean_env.setenv("DOMINO_IS_GIT_BASED", "false")
    http.add("POST", "/api/jobs/v1/jobs", FakeResponse(200, {"job": {"id": "j", "status": {}}}))
    run(server.run_domino_job(OWNER, PROJECT, "python x.py", "t"))
    method, path, kwargs = http.calls[-1]
    assert kwargs["base"] == "http://localhost:8899" and kwargs["headers"] == {}
    assert kwargs["json"]["projectId"] == PID
    assert len(http.calls) == 1   # no project lookup


def test_project_lookup_paginates_until_an_empty_page(server, laptop, http):
    """The server may cap the page size below what was asked; only an empty page ends the scan."""
    pages = {0: [{"id": f"{i:024x}", "name": f"p{i}", "ownerUsername": OWNER} for i in range(10)],
             10: [{"id": f"{i:024x}", "name": f"p{i}", "ownerUsername": OWNER} for i in range(10, 20)],
             20: [{"id": PID, "name": PROJECT, "ownerUsername": OWNER}]}
    seen = []

    def handler(kw):
        seen.append(kw["params"]["offset"])
        return FakeResponse(200, {"projects": pages.get(kw["params"]["offset"], []), "metadata": {}})
    http.add("GET", "/api/projects/beta/projects", handler)
    assert server._resolve_project_id(OWNER, PROJECT) == PID
    assert seen == [0, 10, 20]
    with pytest.raises(server.DominoError) as err:
        server._resolve_project_id(OWNER, "missing")
    assert "not found" in str(err.value)
    assert seen[3:] == [0, 10, 20, 21]        # scanned to the empty page, no premature stop


def test_project_lookup_stops_at_total_count(server, laptop, http):
    seen = []

    def handler(kw):
        seen.append(kw["params"]["offset"])
        return FakeResponse(200, {"projects": [{"id": "a" * 24, "name": "x", "ownerUsername": OWNER}],
                                  "metadata": {"totalCount": 1}})
    http.add("GET", "/api/projects/beta/projects", handler)
    with pytest.raises(server.DominoError):
        server._resolve_project_id(OWNER, "missing")
    assert seen == [0]


def test_project_lookup_gives_up_only_at_the_hard_cap(server, laptop, http, monkeypatch):
    monkeypatch.setattr(server, "_PROJECT_MAX_PAGES", 3)
    http.add("GET", "/api/projects/beta/projects",
             lambda kw: FakeResponse(200, {"projects": [{"id": "a" * 24, "name": "x", "ownerUsername": OWNER}], "metadata": {}}))
    with pytest.raises(server.DominoError) as err:
        server._resolve_project_id(OWNER, "missing")
    assert "Gave up" in str(err.value)


def test_check_job_status_uses_public_job_route(server, laptop, http, run):
    http.add("GET", "/api/jobs/beta/jobs/job1", FakeResponse(200, {"job": {
        "id": "job1", "number": 3, "runCommand": "main.py",
        "status": {"executionStatus": "Succeeded", "isCompleted": True, "isArchived": False, "isScheduled": False},
        "stageTimes": {"completedTime": "2026-05-24T23:29:14.169Z"},
        "dominoStats": [{"name": "R^2", "value": "0.5157"}]}}))
    result = run(server.check_domino_job_run_status("job1", OWNER, PROJECT))
    assert result["status"] == "Succeeded" and result["is_completed"] is True
    assert result["run_id"] == "job1" and result["domino_stats"][0]["name"] == "R^2"
    with pytest.raises(server.DominoError):
        run(server.check_domino_job_run_status("../x"))


def test_check_job_results_pages_logs_and_rewrites_mlflow_url(server, laptop, http, run):
    pages = [
        {"logs": {"logContent": [{"timestamp": "1", "log": "### Starting user code ###"}, {"timestamp": "2", "log": "hello"},
                                 {"timestamp": "3", "log": "View run at: http://127.0.0.1:8768/#/experiments/12/runs/abc123"}],
                  "isComplete": False},
         "metadata": {"pagination": {"limit": 1000, "latestTimeNano": "100"}}},
        {"logs": {"logContent": [{"timestamp": "3", "log": "View run at: http://127.0.0.1:8768/#/experiments/12/runs/abc123"},
                                 {"timestamp": "4", "log": "done"}, {"timestamp": "5", "log": "### User code finished ###"}],
                  "isComplete": True},
         "metadata": {"pagination": {"limit": 1000, "latestTimeNano": "200"}}},
    ]
    seen = []

    def handler(kw):
        seen.append(kw["params"])
        return FakeResponse(200, pages[len(seen) - 1])
    http.add("GET", "/api/jobs/beta/jobs/job1/logs", handler)
    result = run(server.check_domino_job_run_results("job1", OWNER, PROJECT))
    assert seen[0] == {"logType": "stdOut", "limit": server._LOG_PAGE_LIMIT}
    assert seen[1]["latestTimeNano"] == "100"
    assert result["results"] == "hello\ndone"              # boundary line repeated by the cursor is dropped
    assert result["mlflow_url"] == f"https://domino.example.com/experiments/{OWNER}/{PROJECT}/12/abc123"
    assert result["mlflow_path"] == f"/experiments/{OWNER}/{PROJECT}/12/abc123"
    assert result["is_complete"] is True and result["line_count"] == 5


def test_mlflow_link_inside_domino_without_external_host_gives_path_only(server, clean_env, http, run):
    clean_env.setenv("DOMINO_API_PROXY", "http://localhost:8899")
    clean_env.setenv("DOMINO_API_HOST", "http://nucleus-frontend.domino-platform:80")
    http.add("GET", "/api/jobs/beta/jobs/job1/logs", FakeResponse(200, {
        "logs": {"logContent": [{"log": "http://127.0.0.1:8768/#/experiments/1/runs/aa"}], "isComplete": True}, "metadata": {}}))
    result = run(server.check_domino_job_run_results("job1", OWNER, PROJECT))
    assert result["mlflow_path"] == f"/experiments/{OWNER}/{PROJECT}/1/aa" and "mlflow_url" not in result
    clean_env.setenv("VSCODE_PROXY_URI", "https://domino.example.com/vscode/{{port}}/")
    result = run(server.check_domino_job_run_results("job1", OWNER, PROJECT))
    assert result["mlflow_url"] == f"https://domino.example.com/experiments/{OWNER}/{PROJECT}/1/aa"


def test_check_job_results_other_log_types(server, laptop, http, run):
    http.add("GET", "/api/jobs/beta/jobs/job1/logs",
             lambda kw: FakeResponse(200, {"logs": {"logContent": [], "isComplete": True}, "metadata": {}})
             if kw["params"]["logType"] == "stdErr" else FakeResponse(500))
    result = run(server.check_domino_job_run_results("job1", log_type="stdErr"))
    assert result["results"] == "(No output captured)" and "note" in result
    with pytest.raises(server.DominoError):
        run(server.check_domino_job_run_results("job1", log_type="nope"))


# ---------------------------------------------------------------------------------------------
# Files: read on the Public API, list on the Internal API, upload on the legacy v1 API
# ---------------------------------------------------------------------------------------------

def test_list_files_uses_internal_browse_routes(server, laptop, http, run):
    http.add("GET", "/v4/files/browseFiles", FakeResponse(200, [
        {"path": "results/stdout.txt", "name": "stdout.txt", "size": 23, "lastModified": 1, "key": "k", "goalIds": []}]))
    http.add("GET", "/v4/files/browseDirectories", FakeResponse(200, [{"path": "results/sub", "name": "sub", "sizeInBytes": 1}]))
    result = run(server.list_domino_project_files(OWNER, PROJECT, "results"))
    assert result["files"][0]["path"] == "results/stdout.txt" and result["files"][0]["key"] == "k"
    assert result["directories"] == [{"path": "results/sub", "name": "sub"}]
    assert result["count"] == 1 and result["path"] == "results"
    assert http.calls[0][2]["params"] == {"ownerUsername": OWNER, "projectName": PROJECT, "filePath": "results"}


def test_download_reads_nested_path_at_latest_commit(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "scripts/train.py", b"print(1)\n")
    result = run(server.download_file_from_domino_project(OWNER, PROJECT, "/scripts/train.py"))
    assert result["content"] == "print(1)\n" and result["commitId"] == COMMIT
    assert result["key"] == hashlib.sha1(b"print(1)\n").hexdigest()
    assert any(p == f"/api/projects/v1/projects/{PID}/files/{COMMIT}/scripts%2Ftrain.py/content" for _, p, _ in http.calls)
    assert server._file_version_cache[(OWNER, PROJECT, "scripts/train.py")]["key"] == result["key"]


def test_download_missing_file_is_an_error_not_empty_content(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "nope.py", None)
    with pytest.raises(server.DominoError) as err:
        run(server.download_file_from_domino_project(OWNER, PROJECT, "nope.py"))
    assert "does not exist" in str(err.value)
    assert (OWNER, PROJECT, "nope.py") not in server._file_version_cache


@pytest.mark.parametrize("bad", ["", "/", "../etc/passwd", "a/../b", "dir/", "a?b", "a#b"])
def test_path_validation(server, bad):
    with pytest.raises(server.DominoError):
        server._normalize_project_path(bad)


def test_upload_refuses_existing_file_without_overwrite(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "scripts/train.py", b"old")
    _add_upload(http, "scripts/train.py")
    with pytest.raises(server.DominoError) as err:
        run(server.upload_file_to_domino_project(OWNER, PROJECT, "scripts/train.py", "new"))
    assert "already exists" in str(err.value) and "smart_sync_file" in str(err.value)
    assert not _puts(http)
    result = run(server.upload_file_to_domino_project(OWNER, PROJECT, "scripts/train.py", "new", overwrite=True))
    assert result["success"] and result["key"] == hashlib.sha1(b"new").hexdigest()   # local key, not the server's
    method, path, kwargs = http.calls[-1]
    assert (method, path) == ("PUT", f"/v1/projects/{OWNER}/{PROJECT}/scripts/train.py")
    assert kwargs["data"] == b"new"


def test_upload_creates_missing_file_and_reports_no_change(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "new.py", None)
    _add_upload(http, "new.py")
    assert run(server.upload_file_to_domino_project(OWNER, PROJECT, "new.py", "x"))["success"]
    assert len(_puts(http)) == 1
    _add_file(http, "same.py", b"x")
    result = run(server.upload_file_to_domino_project(OWNER, PROJECT, "same.py", "x"))
    assert result["action"] == "no_change" and len(_puts(http)) == 1


def test_sync_local_file_reads_and_uploads(server, laptop, http, run, tmp_path):
    _add_project_lookup(http)
    local = tmp_path / "train.py"
    local.write_text("print('hi')\n")
    _add_file(http, "train.py", None)
    _add_upload(http, "train.py")
    result = run(server.sync_local_file_to_domino(OWNER, PROJECT, str(local)))
    assert result["path"] == "train.py" and http.calls[-1][2]["data"] == b"print('hi')\n"
    with pytest.raises(server.DominoError):
        run(server.sync_local_file_to_domino(OWNER, PROJECT, str(tmp_path / "missing.py")))


# ---------------------------------------------------------------------------------------------
# "Missing" is concluded only from a 404 or a 403 confirmed by the directory listing
# ---------------------------------------------------------------------------------------------

def test_404_means_missing(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "a.py", None, missing_status=404)
    _add_upload(http, "a.py")
    assert run(server.smart_sync_file(OWNER, PROJECT, "a.py", "x"))["action"] == "created"
    assert not any(p == "/v4/files/browseFiles" for _, p, _ in http.calls)


def test_403_with_file_present_in_listing_is_an_error_and_never_overwrites(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "scripts/a.py", None, listing=["scripts/a.py", "scripts/b.py"])
    _add_upload(http, "scripts/a.py")
    for call in (lambda: server.smart_sync_file(OWNER, PROJECT, "scripts/a.py", "x"),
                 lambda: server.smart_sync_file(OWNER, PROJECT, "scripts/a.py", "x", force_overwrite=True),
                 lambda: server.upload_file_to_domino_project(OWNER, PROJECT, "scripts/a.py", "x"),
                 lambda: server.download_file_from_domino_project(OWNER, PROJECT, "scripts/a.py")):
        with pytest.raises(server.DominoError) as err:
            run(call())
        assert "although it exists" in str(err.value) and "Nothing was changed" in str(err.value)
    assert not _puts(http)
    listing_calls = [c for c in http.calls if c[1] == "/v4/files/browseFiles"]
    assert listing_calls and listing_calls[0][2]["params"]["filePath"] == "scripts"


def test_403_with_failing_listing_is_an_error_and_never_overwrites(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "a.py", None)
    http.add("GET", "/v4/files/browseFiles", FakeResponse(403, {"message": "forbidden"}))
    _add_upload(http, "a.py")
    with pytest.raises(server.DominoError) as err:
        run(server.smart_sync_file(OWNER, PROJECT, "a.py", "x", force_overwrite=True))
    assert "HTTP 403" in str(err.value) and not _puts(http)


def test_403_confirmed_absent_by_listing_creates(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "scripts/new.py", None, listing=["scripts/other.py"])
    _add_upload(http, "scripts/new.py")
    assert run(server.smart_sync_file(OWNER, PROJECT, "scripts/new.py", "x"))["action"] == "created"
    assert [c[2]["params"]["filePath"] for c in http.calls if c[1] == "/v4/files/browseFiles"] == ["scripts"]


def test_other_errors_on_read_never_lead_to_an_upload(server, laptop, http, run):
    _add_project_lookup(http)
    http.add("GET", f"/api/projects/beta/projects/{PID}/commits/latest", FakeResponse(200, {"commitId": COMMIT}))
    http.add("GET", f"/api/projects/v1/projects/{PID}/files/{COMMIT}/a.py/content", FakeResponse(500, {"errors": ["boom"]}))
    _add_upload(http, "a.py")
    with pytest.raises(server.DominoError):
        run(server.smart_sync_file(OWNER, PROJECT, "a.py", "x", force_overwrite=True))
    assert not _puts(http)


# ---------------------------------------------------------------------------------------------
# Git-based projects: writes refuse, reads and jobs still work
# ---------------------------------------------------------------------------------------------

def test_write_tools_refuse_git_based_project_from_lookup(server, laptop, http, run, tmp_path):
    _add_project_lookup(http, [{"id": PID, "name": PROJECT, "ownerUsername": OWNER, "mainRepository": GIT_REPO}])
    _add_upload(http, "a.py")
    local = tmp_path / "a.py"
    local.write_text("x")
    for call in (lambda: server.smart_sync_file(OWNER, PROJECT, "a.py", "x", force_overwrite=True),
                 lambda: server.upload_file_to_domino_project(OWNER, PROJECT, "a.py", "x", overwrite=True),
                 lambda: server.sync_local_file_to_domino(OWNER, PROJECT, str(local), overwrite=True)):
        with pytest.raises(server.DominoError) as err:
            run(call())
        assert "Git-based" in str(err.value) and "Commit and push" in str(err.value)
    assert not _puts(http)
    # jobs still start on a Git-based project
    http.add("POST", "/api/jobs/v1/jobs", FakeResponse(200, {"job": {"id": "j", "status": {}}}))
    assert run(server.run_domino_job(OWNER, PROJECT, "python a.py", "t"))["job_id"] == "j"


def test_write_tools_refuse_git_based_project_inside_domino(server, clean_env, http, run):
    clean_env.setenv("DOMINO_API_PROXY", "http://localhost:8899")
    clean_env.setenv("DOMINO_PROJECT_OWNER", OWNER)
    clean_env.setenv("DOMINO_PROJECT_NAME", PROJECT)
    clean_env.setenv("DOMINO_PROJECT_ID", PID)
    clean_env.setenv("DOMINO_IS_GIT_BASED", "true")
    with pytest.raises(server.DominoError) as err:
        run(server.smart_sync_file(OWNER, PROJECT, "a.py", "x"))
    assert "Git-based" in str(err.value) and http.calls == []


def test_inside_domino_without_flag_asks_the_api_whether_git_based(server, clean_env, http, run):
    clean_env.setenv("DOMINO_API_PROXY", "http://localhost:8899")
    clean_env.setenv("DOMINO_PROJECT_OWNER", OWNER)
    clean_env.setenv("DOMINO_PROJECT_NAME", PROJECT)
    clean_env.setenv("DOMINO_PROJECT_ID", PID)
    http.add("GET", f"/api/projects/v1/projects/{PID}",
             FakeResponse(200, {"project": {"id": PID, "name": PROJECT, "ownerUsername": OWNER, "mainRepository": GIT_REPO}}))
    with pytest.raises(server.DominoError) as err:
        run(server.upload_file_to_domino_project(OWNER, PROJECT, "a.py", "x"))
    assert "Git-based" in str(err.value) and not _puts(http)


# ---------------------------------------------------------------------------------------------
# smart_sync_file: never overwrites a file it has not seen
# ---------------------------------------------------------------------------------------------

def test_smart_sync_creates_new_file(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "scripts/new.py", None)
    _add_upload(http, "scripts/new.py")
    result = run(server.smart_sync_file(OWNER, PROJECT, "scripts/new.py", "a = 1\n"))
    assert result["action"] == "created" and result["success"]
    assert len(_puts(http)) == 1
    assert server._file_version_cache[(OWNER, PROJECT, "scripts/new.py")]["key"] == hashlib.sha1(b"a = 1\n").hexdigest()


def test_smart_sync_nested_existing_file_is_a_conflict_not_an_overwrite(server, laptop, http, run):
    """The old implementation listed only the project root, saw nothing for scripts/train.py and
    'created' it, overwriting the remote file. The nested file must be found and protected."""
    _add_project_lookup(http)
    _add_file(http, "scripts/train.py", b"remote version\n")
    _add_upload(http, "scripts/train.py")
    result = run(server.smart_sync_file(OWNER, PROJECT, "scripts/train.py", "my version\n"))
    assert result["conflict"] is True
    assert result["remote_content"] == "remote version\n"
    assert result["remote_key"] == hashlib.sha1(b"remote version\n").hexdigest()
    assert "Nothing was uploaded" in result["message"]
    assert not _puts(http)


def test_smart_sync_identical_content_is_no_change(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "a.py", b"same\n")
    result = run(server.smart_sync_file(OWNER, PROJECT, "a.py", "same\n"))
    assert result["action"] == "no_change" and not _puts(http)


def test_smart_sync_uploads_when_baseline_matches_remote(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "a.py", b"v1\n")
    run(server.download_file_from_domino_project(OWNER, PROJECT, "a.py"))
    _add_upload(http, "a.py")
    result = run(server.smart_sync_file(OWNER, PROJECT, "a.py", "v2\n"))
    assert result["action"] == "uploaded" and http.calls[-1][2]["data"] == b"v2\n"
    assert server._file_version_cache[(OWNER, PROJECT, "a.py")]["key"] == hashlib.sha1(b"v2\n").hexdigest()


def test_smart_sync_detects_remote_change_since_download(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "a.py", b"v1\n")
    run(server.download_file_from_domino_project(OWNER, PROJECT, "a.py"))
    _add_file(http, "a.py", b"someone else\n", commit="ab" * 20)
    _add_upload(http, "a.py")
    result = run(server.smart_sync_file(OWNER, PROJECT, "a.py", "v2\n"))
    assert result["conflict"] is True
    assert result["your_base_key"] == hashlib.sha1(b"v1\n").hexdigest()
    assert result["remote_key"] == hashlib.sha1(b"someone else\n").hexdigest()
    assert result["original_content"] == "v1\n" and result["remote_content"] == "someone else\n"
    assert not _puts(http)


def test_smart_sync_force_overwrite_replaces_and_reports_previous_key(server, laptop, http, run):
    _add_project_lookup(http)
    _add_file(http, "a.py", b"remote\n")
    _add_upload(http, "a.py")
    result = run(server.smart_sync_file(OWNER, PROJECT, "a.py", "mine\n", force_overwrite=True))
    assert result["action"] == "force_overwritten"
    assert result["previous_remote_key"] == hashlib.sha1(b"remote\n").hexdigest()
    assert http.calls[-1][2]["data"] == b"mine\n"


# ---------------------------------------------------------------------------------------------
# Server surface
# ---------------------------------------------------------------------------------------------

def test_tool_names_schemas_and_instructions(server, run):
    tools = {t.name: t for t in run(server.mcp.list_tools())}
    assert set(tools) == {
        "check_domino_job_run_results", "check_domino_job_run_status", "run_domino_job",
        "open_web_browser", "get_domino_environment_info", "list_domino_project_files",
        "upload_file_to_domino_project", "download_file_from_domino_project",
        "sync_local_file_to_domino", "smart_sync_file",
    }
    # the thread wrapper keeps the real signature, so the schema has the real parameters
    assert set(tools["smart_sync_file"].inputSchema["properties"]) == {"user_name", "project_name", "file_path", "content", "force_overwrite"}
    assert tools["smart_sync_file"].inputSchema["required"] == ["user_name", "project_name", "file_path", "content"]
    assert set(tools["run_domino_job"].inputSchema["properties"]) == {"user_name", "project_name", "run_command", "title", "git_branch"}
    assert "conflict detection" in tools["smart_sync_file"].description
    instructions = server._plugin_instructions()
    rules = (Path(server.__file__).resolve().parents[2] / "rules" / "domino.md").read_text(encoding="utf-8")
    lead = rules.split("\n---\n", 2)[-1].split("\n## ", 1)[0].strip()
    assert instructions == lead and instructions.startswith("Domino Data Lab.")
    assert len(lead.encode()) <= 900, "rules/domino.md lead section would be truncated"


def test_tool_errors_are_reported_as_mcp_errors(server, clean_env, run):
    """FastMCP turns a raised DominoError into an isError tool result with the message."""
    from mcp.server.fastmcp.exceptions import ToolError
    with pytest.raises(ToolError) as err:
        run(server.mcp.call_tool("check_domino_job_run_status", {"run_id": "job1"}))
    assert "DOMINO_HOST" in str(err.value)


def test_tools_run_through_fastmcp_with_threaded_wrapper(server, laptop, http, run):
    http.add("GET", "/api/jobs/beta/jobs/job1", FakeResponse(200, {"job": {
        "id": "job1", "status": {"executionStatus": "Running", "isCompleted": False}}}))
    result = run(server.mcp.call_tool("check_domino_job_run_status", {"run_id": "job1"}))
    text = " ".join(getattr(c, "text", "") for c in (result if isinstance(result, list) else result[0]))
    assert '"status": "Running"' in text
