# Coding assistants through LLM Gateway 2.0

Applies to Domino 6.3 and Domino Cloud where an administrator has deployed LLM Gateway 2.0 (early access). Routing a coding assistant through the gateway puts its model calls under the same grants, budgets and usage tracking as any other call. The public docs (https://docs.domino.ai/cloud/platform-capabilities/features/coding-assistants/reuse-credentials#use-with-domino-llm-gateway-2-0) say this is possible and send users to their Domino field representative for the routing details; what follows is only the generic configuration any Anthropic- or OpenAI-compatible gateway needs, expressed in the assistant's own documented settings. Ask the field representative for the setup Domino recommends for your deployment before rolling it out to a team.

Shared facts:

- `<base>` is the gateway App's URL; `<alias>` is a gateway alias the user has a grant for, used as the model name.
- Inside a Workspace the bearer is the access token from `$DOMINO_API_PROXY/access-token` (`http://localhost:8899/access-token`). It is short-lived, so the assistant needs a credential helper that re-fetches it, not a pasted value.
- On a laptop the bearer is a Domino Personal Access Token or a gateway token (`dgw_...`) in an environment variable.
- Assistants make many small requests per turn, so a tight per-user budget refuses them mid-session; plan budgets accordingly.

## Claude Code

Claude Code uses the gateway's Anthropic-compatible path. Its own gateway documentation (https://code.claude.com/docs/en/llm-gateway-connect) defines the three pieces used here: `ANTHROPIC_BASE_URL`, a credential (`ANTHROPIC_AUTH_TOKEN` for a static bearer, or `apiKeyHelper` for one that rotates), and the model name.

### In a Workspace

Use `apiKeyHelper`, which runs a command and sends its output as the bearer. Put it in the project-local settings file, which Claude Code reads when started inside the project directory and keeps out of git (add `.claude/settings.local.json` to `.gitignore` if you create it by hand). Do not overwrite `~/.claude/settings.json`: on environments with home-directory persistence it holds the user's other settings.

```bash
mkdir -p "$DOMINO_WORKING_DIR/.claude"
cat > "$DOMINO_WORKING_DIR/.claude/settings.local.json" <<'EOF'
{
  "env": {
    "ANTHROPIC_BASE_URL": "<base>/anthropic",
    "CLAUDE_CODE_API_KEY_HELPER_TTL_MS": "60000"
  },
  "apiKeyHelper": "curl -sf http://localhost:8899/access-token"
}
EOF
cd "$DOMINO_WORKING_DIR" && claude --model <alias>
```

How the helper behaves (Claude Code settings reference): the output is cached for five minutes by default, or for `CLAUDE_CODE_API_KEY_HELPER_TTL_MS`; it is re-run after that lifetime, when a request fails with 401 or 403, and (from v2.1.246) when the cached output is a JWT that has expired. Set the TTL below the access token's lifetime so a stale token is not sent. The helper's output is sent as both the `Authorization: Bearer` and `X-Api-Key` headers; the gateway reads the bearer.

Credential precedence matters. Claude Code's documented order is `ANTHROPIC_AUTH_TOKEN`, then `ANTHROPIC_API_KEY`, then `apiKeyHelper`, then `CLAUDE_CODE_OAUTH_TOKEN`: a set `ANTHROPIC_AUTH_TOKEN` is used instead of the helper, and a set `ANTHROPIC_API_KEY` outranks the helper too and is sent as `x-api-key`, which the gateway refuses with a 401. Before starting a gateway session, unset both in the shell and check that no Domino user, Project or environment variable sets them (`CLAUDE_CODE_OAUTH_TOKEN` ranks below the helper and is not a problem). Run `/status` in Claude Code to confirm the `Anthropic base URL` line shows the gateway and the credential line names the `apiKeyHelper`.

For a whole team, an administrator can set `ANTHROPIC_BASE_URL` as a Domino environment variable and write the project-local settings file from the Compute Environment's pre-run script (the mechanism the reuse-credentials page describes), writing it only when absent or merging with `jq` so a user's existing project settings survive. Optional attribution: `ANTHROPIC_CUSTOM_HEADERS="X-LLM-Tag-projectname: $DOMINO_PROJECT_NAME"` tags every request with the Project.

### From a laptop

```bash
export ANTHROPIC_BASE_URL="<base>/anthropic"
export ANTHROPIC_AUTH_TOKEN="<Personal Access Token or dgw_ gateway token>"
claude --model <alias>
```

Verify first with the one-token request from the Claude Code gateway page (`POST $ANTHROPIC_BASE_URL/v1/messages` with `Authorization: Bearer`); an error naming an unknown model still proves the URL and credential work.

### Claude Code specifics

- Claude Code also calls a smaller model for background work (titles, summaries) by that model's own name; if the gateway has no alias of that exact name, those calls fail quietly and only the main conversation works. Ask the administrator to publish an alias with that name if titles and summaries matter.
- Which Anthropic features reach the model (prompt caching, extended thinking, native tool use) depends on the provider behind the alias; ask the administrator what the alias is backed by.

## Other hosts

Any assistant that accepts an OpenAI-compatible base URL (`<base>/v1`) or an Anthropic-compatible one (`<base>/anthropic`) plus a bearer token can be pointed at the gateway: configure it the way that host documents, with the alias as the model and, inside Domino, a credential helper rather than a pasted token. Codex, for example, supports custom model providers in its configuration, but routing Codex through the gateway has not been tested; ask the Domino field representative before relying on it. Hosts that cannot change their API endpoint, or that only accept their vendor's own key, cannot be routed through the gateway.
