# Coding assistants through LLM Gateway 2.0

Applies to Domino 6.3 and Domino Cloud where an administrator has deployed LLM Gateway 2.0. Routing a coding assistant through the gateway puts its model calls under the same grants, budgets, guardrails and usage logging as any other call; each request shows up in the gateway's usage dashboard with user, Project, alias, cost and latency. The docs page https://docs.domino.ai/cloud/platform-capabilities/features/coding-assistants/reuse-credentials#use-with-domino-llm-gateway-2-0 describes the intent; the setup below is per host.

Shared facts:

- `<base>` is the gateway App's URL (`https://<domino or apps host>/apps/<app id or vanity URL>`); `<alias>` is a gateway alias the user has a grant for.
- Inside a Workspace the bearer is the access token from `$DOMINO_API_PROXY/access-token` (`http://localhost:8899/access-token`); it expires in minutes, so the host must re-fetch it per request through a token-helper command, not a static variable.
- On a laptop the bearer is a Domino Personal Access Token or a gateway token (`dgw_...`) in an environment variable.
- Assistants make many small requests per turn, so a tight per-user budget denies them mid-session; plan budgets accordingly.

## Claude Code

Claude Code talks to the gateway's Anthropic-compatible path, `<base>/anthropic`. Three settings do the work: `ANTHROPIC_BASE_URL`, a bearer (the `apiKeyHelper` setting, which runs a command per request and sends its output as `Authorization: Bearer`, or `ANTHROPIC_AUTH_TOKEN` for a static token), and `claude --model <alias>`. Two optional ones help: `CLAUDE_CODE_ATTRIBUTION_HEADER=0` keeps the system prompt byte-stable so provider prompt caching can hit, and `ANTHROPIC_CUSTOM_HEADERS="X-LLM-Tag-projectname: <project>"` tags every request for attribution.

### In a Workspace, for a whole Compute Environment (administrator or environment owner)

Put this in the Compute Environment's **Pre Run Script** (**Environments** > edit definition > run setup scripts). It runs at Workspace start as the Workspace user, after Domino's environment variables exist. Fill in `<base>`:

```bash
# Environment variables, sourced by interactive shells
cat > "$HOME/.anthropic-gateway.sh" <<'EOF'
export ANTHROPIC_BASE_URL="<base>/anthropic"
export CLAUDE_CODE_ATTRIBUTION_HEADER=0
if [ -n "$DOMINO_PROJECT_NAME" ]; then
  export ANTHROPIC_CUSTOM_HEADERS="X-LLM-Tag-projectname: $DOMINO_PROJECT_NAME"
fi
EOF
MARKER="# >>> domino llm gateway >>>"
grep -qF "$MARKER" "$HOME/.bashrc" 2>/dev/null || cat >> "$HOME/.bashrc" <<EOF

$MARKER
[ -f "\$HOME/.anthropic-gateway.sh" ] && . "\$HOME/.anthropic-gateway.sh"
# <<< domino llm gateway <<<
EOF

# apiKeyHelper must live in a settings file. Project-scoped settings.local.json is picked up
# when Claude Code starts inside the project directory (DOMINO_WORKING_DIR: /mnt/code for
# Git-based projects, /mnt for DFS).
CODE_DIR="${DOMINO_WORKING_DIR:-/mnt}"
mkdir -p "$CODE_DIR/.claude"
cat > "$CODE_DIR/.claude/settings.local.json" <<'EOF'
{
  "apiKeyHelper": "curl -sf http://localhost:8899/access-token"
}
EOF
```

Then, in a new Workspace, `cd` into the project directory and run `claude --model <alias>`. Verify with `echo "$ANTHROPIC_BASE_URL"`, `cat "$DOMINO_WORKING_DIR/.claude/settings.local.json"` and `curl -sf http://localhost:8899/access-token | head -c 20`.

Things to know:

- `settings.local.json` is rewritten at every Workspace start; add `.claude/settings.local.json` to `.gitignore` in Git-based projects. Users' own settings belong in `.claude/settings.json`, which the script does not touch.
- Launch Claude Code from the project directory (or a subdirectory); elsewhere it does not see the project-scoped settings and falls back to whatever credential the environment has.
- Shells that do not source `~/.bashrc` need the same source line in `~/.profile`.

### In a single Workspace, by hand

User-scoped settings instead of the Pre Run Script:

```bash
mkdir -p "$HOME/.claude"
cat > "$HOME/.claude/settings.json" <<EOF
{
  "env": {
    "ANTHROPIC_BASE_URL": "<base>/anthropic",
    "ANTHROPIC_CUSTOM_HEADERS": "X-LLM-Tag-projectname: ${DOMINO_PROJECT_NAME}",
    "CLAUDE_CODE_ATTRIBUTION_HEADER": "0"
  },
  "apiKeyHelper": "curl -sf http://localhost:8899/access-token"
}
EOF
claude --model <alias>
```

The unquoted heredoc expands `${DOMINO_PROJECT_NAME}` at write time. `apiKeyHelper` is preferred over a static `ANTHROPIC_AUTH_TOKEN` inside Domino because the access token expires quickly.

### From a laptop

No sidecar, so use a static token:

```bash
export ANTHROPIC_BASE_URL="<base>/anthropic"
export ANTHROPIC_AUTH_TOKEN="<Personal Access Token or dgw_ gateway token>"
export CLAUDE_CODE_ATTRIBUTION_HEADER=0
export ANTHROPIC_CUSTOM_HEADERS="X-LLM-Tag-projectname: <project>"   # optional
claude --model <alias>
```

### Claude Code specifics

- Claude Code makes background calls (titles, compaction, tool-result summaries) to its default small model by that model's canonical Anthropic name. If only a large-model alias exists, those calls fail with 404 in the gateway log and titles and summaries degrade; the fix is an alias named exactly like Claude Code's current default small model, pointing at any provider that serves it.
- Sessions are aggregatable in the gateway's usage views by the session tag the gateway records from Claude Code's session header.
- Aliases that resolve to non-Anthropic providers are translated to the OpenAI format: tool use and vision work; prompt-cache markers and extended thinking are dropped.
- If `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` is also set (user, Project or environment variables), check which credential wins before assuming traffic goes through the gateway.

## Codex

Codex can use any provider that speaks the OpenAI Responses API, and the gateway serves it at `<base>/v1/responses`. Define a custom provider in `~/.codex/config.toml` (Codex's documented `model_providers` table; `wire_api` is `responses`, the only supported value):

```toml
model = "<alias>"
model_provider = "domino-gateway"

[model_providers.domino-gateway]
name = "Domino LLM Gateway"
base_url = "<base>/v1"
wire_api = "responses"
http_headers = { "X-LLM-Tag-team" = "research" }     # optional attribution

# Inside a Domino Workspace: a command-backed bearer, re-run whenever Codex needs a token
[model_providers.domino-gateway.auth]
command = "curl"
args = ["-sf", "http://localhost:8899/access-token"]
```

On a laptop, replace the `auth` table with a static token from the environment (do not combine the two):

```toml
[model_providers.domino-gateway]
name = "Domino LLM Gateway"
base_url = "<base>/v1"
wire_api = "responses"
env_key = "DOMINO_GATEWAY_TOKEN"        # a Personal Access Token or dgw_ gateway token
```

Codex sends the alias as the model, so `<alias>` must exist in the gateway and the user must hold a grant. To make the Workspace setup automatic, write `~/.codex/config.toml` from the Compute Environment's Pre Run Script the same way as the Claude Code snippet above; keep any `CODEX_AUTH_JSON` subscription seeding (see the docs page above) out of the picture when the gateway should serve the traffic.

## Other hosts

Any assistant that accepts an OpenAI-compatible base URL (`<base>/v1`) or an Anthropic-compatible one (`<base>/anthropic`) plus a bearer token can use the gateway: configure it the way that host documents, with the alias as the model and, inside Domino, a token helper rather than a pasted token. Hosts that cannot change their API endpoint or that only accept their vendor's own key cannot be routed through the gateway.
