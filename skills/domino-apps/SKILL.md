---
name: domino-apps
description: Deploy web applications to Domino behind its reverse proxy. Covers the app.sh entry point, the required 0.0.0.0:8888 binding, DOMINO_RUN_HOST_PATH path prefixes, Vite + React (relative base, HashRouter, a small backend for model calls), Streamlit, Dash, Flask, Shiny, Gradio and FastAPI setup, the Apps v1 REST publish chain, CI/CD with GitHub Actions, and proxy troubleshooting. Use when publishing or deploying an app to Domino, automating app create, start or stop over the API, building a CI/CD pipeline for a Domino app, fixing 404s, blank pages or broken routing behind the proxy, or configuring a web framework for Domino.
compatibility: Domino 6.3 and Domino Cloud. Requires DOMINO_API_HOST; in a run use DOMINO_API_PROXY or the localhost:8899 access-token endpoint, outside a run a Personal Access Token or service account token.
---

# Domino Apps

Applies to Domino 6.3 and Domino Cloud. Routes, environment variables and proxy behaviour are the same on both targets.

A Domino App runs project code in a container behind Domino's reverse proxy. The proxy authenticates the viewer, strips the App's URL prefix before forwarding the request, and adds the `domino-username` header (plus an `Authorization` JWT when secure identity propagation is on, which is the default on 6.3 and Cloud).

## Rules every App must satisfy

1. **Serve on `0.0.0.0:8888`.** An App that does not expose a server on that address and port fails to start. Port 8888 is mandatory, not a default.
2. **The entry point is a launch file** in the project (`app.sh`, or a Python or R script). It is fixed for the life of the App; create a new App to change it.
3. **Read the URL prefix from `DOMINO_RUN_HOST_PATH`** wherever a framework needs its base path (Dash `requests_pathname_prefix`, Gradio `root_path`). Never assemble it from `DOMINO_PROJECT_OWNER`, `DOMINO_PROJECT_NAME` and `DOMINO_RUN_ID`; that prefix stopped matching when `SecureIdentityPropagationToAppsEnabled` became the default.
4. **Use relative URLs** for assets and API calls (Vite `base: './'`, `new URL('api/', document.baseURI)`), never root-absolute `/assets/...` or `fetch('/api/...')`.
5. **Keep secrets on the server.** Model endpoint tokens live in project or user environment variables and are read by backend code. Anything in a `VITE_`-prefixed variable is compiled into the browser bundle.

## Quick start

| Framework | `app.sh` runs | Details |
|---|---|---|
| Vite + React | `npm ci && npm run build && node server.js` (Express serves `dist/` and proxies model calls), or `npx serve -s dist -l 8888` when the app calls nothing | [REACT-VITE-GUIDE.md](./REACT-VITE-GUIDE.md) |
| Streamlit | `streamlit run app.py --server.port 8888 --server.address 0.0.0.0 --server.enableCORS false --server.enableXsrfProtection false` | [FRAMEWORKS.md](./FRAMEWORKS.md) |
| Dash | `python app.py` with `Dash(__name__, routes_pathname_prefix='/', requests_pathname_prefix=os.environ.get('DOMINO_RUN_HOST_PATH'))` and `app.run(host='0.0.0.0', port=8888)` | [FRAMEWORKS.md](./FRAMEWORKS.md) |
| Flask | `python -m flask run --host=0.0.0.0 --port=8888` or `gunicorn -w 4 -b 0.0.0.0:8888 app:app` | [FRAMEWORKS.md](./FRAMEWORKS.md) |
| Shiny | `R -e 'shiny::runApp("./", port=8888, host="0.0.0.0")'` | [FRAMEWORKS.md](./FRAMEWORKS.md) |

Scaffold any of these with the `domino-app-init` skill; diagnose a broken deployment with `domino-debug-proxy`.

```javascript
// vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',
  server: { host: '0.0.0.0', port: 8888, strictPort: true },
  preview: { host: '0.0.0.0', port: 8888, strictPort: true },
})
```

Use `HashRouter` for client-side routes: they live after `#`, so they never reach the server and relative asset URLs resolve from the App root on every route. `BrowserRouter` with a basename derived from `window.location.pathname` breaks on nested routes.

## Lifecycle

Create, publish and deploy are separate steps. Publishing records an immutable version (code commit, environment revision, data plane, mounts, identity propagation); deploying starts it. Hardware tier, autoscaling, vanity URL and iframe settings are deployment settings: changing them restarts the instance without creating a version. Develop in a workspace with **App Preview** (a real App runtime on port 8888, visible only to the author at `/preview/<draftAppId>`), then **Publish App**, then **Deploy** the version from the App details page.

## Environment variables and headers

| Name | Meaning |
|---|---|
| `DOMINO_RUN_HOST_PATH` | URL path prefix under which the App is served |
| `DOMINO_PROJECT_ID`, `DOMINO_PROJECT_NAME`, `DOMINO_PROJECT_OWNER` | Hosting project |
| `DOMINO_RUN_ID` | Run ID of the App instance |
| `DOMINO_STARTING_USERNAME` | User who started the run, not the viewer |
| `DOMINO_WORKING_DIR` | Directory holding the project files |
| `DOMINO_API_HOST` | Base URL for Domino platform APIs from inside the App |
| `domino-username` (request header) | Viewer's username; `Anonymous` when anonymous access is enabled |
| `Authorization` (request header) | Viewer JWT; full user scope only with extended identity propagation and viewer consent |

Project and user-level environment variables are injected at start. Flask and Dash read the proxied headers by default; Shiny needs Shiny Server Pro.

## Calling Domino APIs and model endpoints from an App

- **Platform API as the publisher**: `$DOMINO_API_PROXY/api/...` with no `Authorization` header, or a bearer from `http://localhost:8899/access-token` on `$DOMINO_API_HOST`. Fetch the token per request; it is short-lived.
- **Platform API as the viewer**: with extended identity propagation enabled by a SysAdmin or CloudAdmin and consent granted, forward the viewer's `Authorization` header.
- **Model endpoints**: read `MODEL_API_URL` and `MODEL_API_TOKEN` from environment variables set in project settings. Tokens are created per endpoint under **Settings > Invocation > Add Model Access Token**. Synchronous endpoints take HTTP Basic auth with the token as both username and password (`requests.post(url, auth=(token, token), json={"data": {...}})`); asynchronous endpoints take `Authorization: Bearer <token>`. Call them from backend code, never from the browser.

Authentication reference: https://docs.domino.ai/cloud/reference/api/domino-api-authentication . Legacy API keys (`DOMINO_USER_API_KEY`, `X-Domino-Api-Key`) are deprecated; do not use them.

## REST automation

`/api/apps/v1` for create, versions, publish (drafts), start and stop; `/api/apps/beta` only for instance reads (list instances, logs, real-time logs, views). The create body requires `name`, `projectId` and `visibility`. Full chain, bodies and the logs route: [API-APPS.md](./API-APPS.md). CI/CD with GitHub Actions and a service account: [REACT-CICD.md](./REACT-CICD.md).

## Reference files

- [REACT-VITE-GUIDE.md](./REACT-VITE-GUIDE.md): Vite config, Express backend that keeps the model token server-side, HashRouter, App Preview workflow
- [REACT-CICD.md](./REACT-CICD.md): GitHub Actions workflow and a Public API deploy script
- [FRAMEWORKS.md](./FRAMEWORKS.md): Streamlit, Dash, Flask, Gradio, FastAPI and Shiny configurations
- [API-APPS.md](./API-APPS.md): v1 vs beta routes, publish chain, logs
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md): symptoms, causes and fixes

Docs: https://docs.domino.ai/cloud/platform-capabilities/features/apps (Cloud) and https://docs.domino.ai/6.3/platform-capabilities/features/apps (6.3). Specs: https://docs.domino.ai/api-specs/cloud/public-api.json and https://docs.domino.ai/api-specs/6.3/public-api.json . Related skills: `domino-api-intro` (auth and hosts), `domino-ui-bootstrap` (Domino design system SPA), `domino-ui-design` (FastAPI + Ant Design UI), `domino-extensions` (mount an App in the Domino UI).
