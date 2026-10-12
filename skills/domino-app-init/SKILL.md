---
name: domino-app-init
description: Scaffold a new Domino-ready web application (Vite + React, Streamlit, Dash, Flask, Gradio or FastAPI) with the settings Domino's reverse proxy needs, the mandatory 0.0.0.0:8888 binding, DOMINO_RUN_HOST_PATH prefixes, server-side model endpoint calls, and an app.sh entry point. Use when the user wants to start, initialize, create or scaffold a new app to publish on Domino, or asks for a starter app.sh or starter app for a web framework on Domino.
compatibility: Domino 6.3 and Domino Cloud. Templates only; no API calls. Publishing the result needs a Domino project and a Compute Environment that contains the framework (and Node for Vite).
---

# Initialize a Domino App

Applies to Domino 6.3 and Domino Cloud.

Create a web application that works behind Domino's reverse proxy on the first publish.

## Inputs

Collect these before writing files. Skip any the user has already given.

1. **Framework**: `vite-react` (default), `streamlit`, `dash`, `flask`, `gradio` or `fastapi`.
2. **Project name**: app folder name and `package.json` name (React only).
3. **Model endpoint integration**: whether the app calls a Domino endpoint. If yes, the call goes through backend code; the user sets `MODEL_API_URL` and `MODEL_API_TOKEN` in Domino, never in the repository.

If the target directory already contains an app, stop and ask before overwriting anything.

## Steps

1. Copy the matching template from this skill's `assets/` folder into the project:

   | Framework | Files to copy |
   |---|---|
   | `vite-react` | `assets/vite-react/vite.config.js`, `assets/vite-react/app.sh`, `assets/vite-react/server.js`, `assets/vite-react/.env.example` (run `npm create vite@latest` first if there is no Vite project yet, then `npm install express` and `npm install -D serve`) |
   | `streamlit` | `assets/streamlit/app.sh`, and `assets/streamlit/app.py.template` saved as `app.py` |
   | `dash` | `assets/dash/app.sh`, and `assets/dash/app.py.template` saved as `app.py` |
   | `flask`, `gradio`, `fastapi` | No template; write the files from the snippets below |

2. Make `app.sh` executable (`chmod +x app.sh`) and commit the mode (`git update-index --chmod=+x app.sh`). The templates start with `cd "$(dirname "$0")"`, so `app.sh` works from the repo root or from the app subfolder; the user selects it as the App file either way.
3. Keep these invariants in every generated file:
   - Bind `0.0.0.0` on port `8888`. Domino requires both; an App on any other address or port fails to start.
   - Where the framework needs its base path, read `DOMINO_RUN_HOST_PATH` (Dash `requests_pathname_prefix`, Gradio `root_path`). Never build the prefix from project owner, name and run ID.
   - Use relative URLs for assets and API calls. For Vite set `base: './'` and use `HashRouter`.
   - Secrets stay on the server: no token in a `VITE_` variable, no token in the repo.
4. Add `.env`, `.env.local`, `node_modules/` and `dist/` to `.gitignore`; keep `.env.example`.
5. Finish with the post-initialization checklist.

## Reference snippets

### Dash: `app.py` (Dash 3 removed `run_server`)

```python
import os
from dash import Dash, html

app = Dash(__name__, routes_pathname_prefix="/",
           requests_pathname_prefix=os.environ.get("DOMINO_RUN_HOST_PATH"))
app.layout = html.Div([html.H1("Domino Dash App")])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=False)
```

### Flask: `app.py` and `app.sh`

```python
from flask import Flask, request

app = Flask(__name__)

@app.route("/")
def index():
    return f"Hello {request.headers.get('domino-username', 'Anonymous')}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=False)
```

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"
python app.py
```

### Gradio: `app.py` (same `app.sh` as Flask)

```python
import os
import gradio as gr

demo = gr.Interface(fn=lambda text: text, inputs="text", outputs="text")

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8888,
                root_path=os.environ.get("DOMINO_RUN_HOST_PATH", ""))
```

### FastAPI: `app.py` and `app.sh`

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def index():
    return {"message": "Domino FastAPI App"}
```

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"
uvicorn app:app --host 0.0.0.0 --port 8888
```

### Model endpoint call (any Python framework)

```python
import os, requests
token = os.environ["MODEL_API_TOKEN"]
resp = requests.post(os.environ["MODEL_API_URL"], auth=(token, token),   # synchronous endpoint
                     json={"data": {"feature1": 1.0}}, timeout=60)
```

Synchronous endpoints use HTTP Basic with the token as username and password; asynchronous endpoints use `Authorization: Bearer`. The React template does the same in `server.js`.

## Post-initialization checklist

Tell the user to:

1. Set `MODEL_API_URL` and `MODEL_API_TOKEN` (if used) as environment variables in the Domino project settings. The token comes from the endpoint's **Settings > Invocation > Add Model Access Token**.
2. Confirm the Compute Environment contains the framework (and Node for Vite); `app.sh` should not `pip install` at start.
3. In a workspace, open **App Preview**, select `app.sh`, and test. Preview runs the real App runtime, including the proxy prefix.
4. **Publish App**, then **Deploy** the version from the App details page and set sharing.

For deployment details, CI/CD and framework specifics use the `domino-apps` skill; for 404s, blank pages or routing problems after publishing use `domino-debug-proxy`; for a Domino design system SPA use `domino-ui-bootstrap`.
