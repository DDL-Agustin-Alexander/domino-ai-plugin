"""Shared fixtures: import the server module with a clean environment and a fake HTTP layer."""
import asyncio
import importlib
import json as jsonlib
import os
import sys
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

_ENV_NAMES = (
    "DOMINO_API_HOST", "DOMINO_API_PROXY", "DOMINO_HOST", "DOMINO_TOKEN", "DOMINO_API_KEY",
    "DOMINO_PROJECT_ID", "DOMINO_PROJECT_NAME", "DOMINO_PROJECT_OWNER", "DOMINO_IS_GIT_BASED",
    "DOMINO_WORKING_DIR", "DOMINO_RUN_ID", "DOMINO_USER_HOST", "VSCODE_PROXY_URI",
    "DOMINO_MCP_ENV_FILE", "XDG_CONFIG_HOME",
)


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """No Domino variables, no env file."""
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DOMINO_MCP_ENV_FILE", str(tmp_path / "absent.env"))
    return monkeypatch


@pytest.fixture
def server(clean_env):
    """A freshly imported server module (import-time environment handling runs under clean_env)."""
    sys.modules.pop("domino_mcp_server", None)
    module = importlib.import_module("domino_mcp_server")
    module._project_id_cache.clear()
    module._file_version_cache.clear()
    return module


class FakeResponse:
    def __init__(self, status_code=200, json_body=None, content=b"", text=None):
        self.status_code = status_code
        self._json = json_body
        if json_body is not None and not content:
            content = jsonlib.dumps(json_body).encode()
        self.content = content
        self.text = text if text is not None else content.decode("utf-8", "replace")

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class FakeHTTP:
    """Routes requests.request(method, url, ...) to canned responses and records every call."""

    def __init__(self):
        self.routes = {}   # (METHOD, path) -> FakeResponse | callable(kwargs) -> FakeResponse
        self.calls = []    # (METHOD, path, kwargs)

    def add(self, method, path, response):
        self.routes[(method.upper(), path)] = response

    def __call__(self, method, url, **kwargs):
        from urllib.parse import urlsplit
        parts = urlsplit(url)
        self.calls.append((method.upper(), parts.path, {**kwargs, "base": f"{parts.scheme}://{parts.netloc}"}))
        route = self.routes.get((method.upper(), parts.path))
        if route is None:
            return FakeResponse(404, {"errors": [f"no fake route for {method} {parts.path}"]})
        return route(kwargs) if callable(route) else route


@pytest.fixture
def http(server, monkeypatch):
    fake = FakeHTTP()
    monkeypatch.setattr(server.requests, "request", fake)
    return fake


@pytest.fixture
def run():
    return lambda coro: asyncio.run(coro)
