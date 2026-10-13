---
name: domino-debug-proxy
description: Diagnose and fix Domino reverse-proxy and routing problems in published web apps by checking vite.config.js, package.json, app.sh, server.js and Python entry points (app.py) for the wrong port, localhost binding, absolute base paths, a hand-built URL prefix instead of DOMINO_RUN_HOST_PATH, BrowserRouter deep links, missing build steps, or a model token compiled into the browser bundle. Use when a Domino app never reaches Running, shows connection refused, 404s on CSS or JS assets, a blank page, broken deep links, or stopped working after a restart.
compatibility: Domino 6.3 and Domino Cloud. Reads project files; the optional log check needs DOMINO_API_HOST and the localhost:8899 access-token endpoint in a run, or a Personal Access Token outside one.
---

# Debug Domino App proxy issues

Applies to Domino 6.3 and Domino Cloud.

Find the configuration mistakes that break apps behind Domino's reverse proxy, report them, and fix them with the user's agreement. The proxy authenticates viewers, strips the App's URL prefix, forwards to the container on port 8888, and adds the `domino-username` header.

## Steps

1. Locate the app's files: `app.sh` (or the Python/R entry point Domino runs), `vite.config.js` or `vite.config.ts`, `package.json`, `server.js`, `src/main.jsx` or `main.tsx`, and `app.py`.
2. Run every check below and record each result as pass or fail.
3. Print a report in the format shown under "Report format".
4. List the recommended fixes and ask whether to apply them. Apply only what the user approves.
5. For anything you can't fix from config, give the manual investigation steps.

## Checks

| # | Check | Pass condition |
|---|---|---|
| 1 | Port and host | The process Domino starts listens on `0.0.0.0:8888` (`serve -l 8888`, `app.listen(8888, '0.0.0.0')`, `--server.port 8888 --server.address 0.0.0.0`, `app.run(host="0.0.0.0", port=8888)`, `uvicorn --host 0.0.0.0 --port 8888`). Domino rejects any other address or port |
| 2 | Base path | Vite sets `base: './'`; HTML templates reference `static/...`, never `/static/...` |
| 3 | Router | React Router uses `HashRouter` (pass). `BrowserRouter` is a warning, not a failure: it works only with an SPA fallback on the server (`serve -s` or the Express fallback) and an absolute `base` (`DOMINO_RUN_HOST_PATH` at build time, since `app.sh` builds inside the App container) instead of `./`; with the relative `base` it breaks assets on nested routes |
| 4 | `app.sh` | Executable (`git update-index --chmod=+x app.sh`), changes to its own directory (`cd "$(dirname "$0")"`) or the project directory, runs `npm ci` and `npm run build` before serving, and does not `pip install` or `npm install` packages the Compute Environment should contain |
| 5 | Prefix | Python frameworks that need a base path read `DOMINO_RUN_HOST_PATH` (Dash `requests_pathname_prefix`, Gradio `root_path`); nothing concatenates `DOMINO_PROJECT_OWNER`, `DOMINO_PROJECT_NAME` and `DOMINO_RUN_ID` into a path |
| 6 | Asset and API references | No root-absolute `fetch('/api/...')` or `/assets/...`; frontend API calls resolve with `new URL('api/', document.baseURI)` |
| 7 | Secrets | No `VITE_*_TOKEN` or `VITE_*_KEY` in `.env*`, workflow files or source; model endpoint calls happen in `server.js`, Flask, FastAPI or another backend. Synchronous endpoints use HTTP Basic (token as user and password), asynchronous ones Bearer |
| 8 | Dash API | `app.run(...)`, not `app.run_server(...)` (removed in Dash 3) |

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| Never reaches Running | Bound to `localhost` or a port other than 8888 | Listen on `0.0.0.0:8888` |
| 404 on CSS and JS | `base` is `/` or missing | `base: './'` in `defineConfig`; rebuild and republish |
| Deep links or refresh return 404 | `BrowserRouter` routes reach the server | Switch to `HashRouter`, or keep `BrowserRouter` with `serve -s` and an absolute `base` from `DOMINO_RUN_HOST_PATH` |
| Blank page or stale content | `app.sh` has no build step, or the App was not republished after the change | Add `npm run build` before serving; publish a new version and deploy it |
| Worked, then failed after a restart | Hand-built prefix instead of `DOMINO_RUN_HOST_PATH` | Read the prefix from `DOMINO_RUN_HOST_PATH` |
| Model call 401 | Bearer sent to a synchronous endpoint, or token missing | Basic auth with the Model Access Token as user and password; set `MODEL_API_TOKEN` in project settings and restart |
| Model call CORS error | Browser calls the endpoint directly | Route it through the backend |
| `import.meta.env.VITE_X` undefined | Variable not set when `npm run build` ran, or no `VITE_` prefix | Prefix non-secret build-time values; keep runtime values server-side |

A corrected `app.sh` for a Vite app with a backend:

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"
npm ci
npm run build
node server.js      # or: npx serve -s dist -l 8888 --no-clipboard
```

## Report format

```
Domino Proxy Debug Report
=========================

Checking: vite.config.js
PASS Port: 8888, host 0.0.0.0
PASS Base path: './'

Checking: src/main.jsx
WARN Router: BrowserRouter with base './' (deep links 404; nested routes break assets)

Checking: app.sh
PASS Working directory: cd "$(dirname "$0")"
PASS Build command: npm run build
FAIL Serve command missing -s flag

Summary: 1 issue, 1 warning

Recommended fixes:
1. Replace BrowserRouter with HashRouter in src/main.jsx (or keep it with serve -s and an absolute base)
2. Update the app.sh serve command:
   - Current: npx serve dist -l 8888
   + Fixed:   npx serve -s dist -l 8888
```

## Manual investigation

If the config is correct but the app still fails:

1. Read the App logs on the App details page (instance selector; support bundle for Kubernetes and nginx logs). Over the API: `GET /api/apps/beta/apps/{appId}/versions/{versionId}/instances`, then `GET .../instances/{instanceId}/logs?logType=stderr` with a bearer from `http://localhost:8899/access-token` (or a Personal Access Token outside a run).
2. In the browser developer tools, check whether failing requests dropped the App's URL prefix (the path before the app's own routes) or went to another host.
3. Confirm the App was republished after the last commit: a version pins a commit, and deploying an old version serves old code.
4. Test in a workspace with **App Preview**, which runs the real proxy and `DOMINO_RUN_HOST_PATH`; a local `npm run dev` cannot reproduce them.

For general deployment guidance, framework configs and the REST routes, use the `domino-apps` skill.
