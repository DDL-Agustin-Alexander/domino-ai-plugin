# Domino plugin hooks

Claude Code hooks are commands (or HTTP endpoints, MCP tools, prompts and agents) that run at
lifecycle events such as a tool call. This directory documents hooks that are useful around
Domino work. **Nothing in it is loaded.** The plugin ships no `hooks/hooks.json`; its only hook
is the inline `SessionStart` entry in `.claude-plugin/plugin.json`, which prints `rules/domino.md`
into every session. Leave that entry as it is. Hooks stay out of the package on purpose: a plugin
that bundles lifecycle hooks isn't eligible for the OpenAI public plugin directory.

Reference: [Hooks](https://code.claude.com/docs/en/hooks) (format, events, input and output) and
[Plugin components: hooks](https://code.claude.com/docs/en/plugins/components#hooks).

## Where hooks live

| File | Scope |
| --- | --- |
| `~/.claude/settings.json` | All your projects |
| `.claude/settings.json` | One project; commit it to share with the team |
| `.claude/settings.local.json` | One project, not committed |
| `hooks/hooks.json` inside a plugin | While that plugin is enabled |

There is no `.claude/hooks.json`. Hooks are the `hooks` key of a settings file, and Claude Code
picks up edits to settings files without a restart.

## Format

A hooks block has three levels: the **event** (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`,
`SessionStart`, `Stop`, and others), a **matcher group** that filters it (for tool events the
tool name: `Write`, `Edit|Write`, `Bash`, or a regular expression), and the **handlers** to run.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-python.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

A command hook receives the event as **JSON on stdin**, not as environment variables. For `Write`
the input carries `tool_input.file_path` and `tool_input.content`; for `Edit` it carries
`tool_input.file_path`, `tool_input.old_string` and `tool_input.new_string`; `PostToolUse` adds
`tool_response`. `file_path` is always absolute. Read it with `jq`:

```bash
input=$(cat)
file=$(jq -r '.tool_input.file_path // empty' <<<"$input")
```

Exit codes: `0` lets the action proceed; on most events stdout then goes to the debug log, not to
the model, except on `SessionStart`, `UserPromptSubmit`, `UserPromptExpansion` and
`PostModelSwitch`, where plain stdout is added as context (that is how the plugin's `SessionStart`
hook delivers `rules/domino.md`). `2` is a blocking error whose stderr the model sees. On `PreToolUse`, exit 2 blocks the tool call; on
`PostToolUse` the tool has already run and the stderr arrives as feedback the model acts on. Any
other exit code is a non-blocking error. `$CLAUDE_PROJECT_DIR` is the project root where the
session started, so scripts can be referenced from any working directory; `timeout` is in seconds
(default 600 for command hooks). All matching hooks run in parallel.

## Examples

Each example is a script plus the settings entry that registers it. Save the scripts under
`.claude/hooks/` in your project and make them executable (`chmod +x`). They need `jq`.

### Warn when app.sh does not bind to 0.0.0.0

Domino's reverse proxy reaches an App only on `0.0.0.0:8888` (see `skills/domino-apps/`). This
`PostToolUse` hook lets the write happen and tells the model when the file misses it.

`.claude/hooks/check-app-sh.sh`:

```bash
#!/bin/bash
input=$(cat)
file=$(jq -r '.tool_input.file_path // empty' <<<"$input")
[[ "$file" == */app.sh ]] || exit 0
if ! grep -q '0\.0\.0\.0' "$file"; then
  echo "app.sh must start the server on 0.0.0.0 (port 8888) for Domino's reverse proxy; localhost will not work" >&2
  exit 2
fi
```

Settings:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-app-sh.sh" }
        ]
      }
    ]
  }
}
```

To refuse the write instead of warning after it, register the script under `PreToolUse` with
matcher `Write` and test `tool_input.content`, because the file doesn't exist yet:

```bash
content=$(jq -r '.tool_input.content // empty' <<<"$input")
grep -q '0\.0\.0\.0' <<<"$content" || { echo "app.sh must bind to 0.0.0.0" >&2; exit 2; }
```

### Check Python syntax after an edit

`.claude/hooks/check-python.sh`:

```bash
#!/bin/bash
input=$(cat)
file=$(jq -r '.tool_input.file_path // empty' <<<"$input")
[[ "$file" == *.py ]] || exit 0
# ast.parse reports a SyntaxError on stderr (which reaches the model) and, unlike py_compile,
# writes no __pycache__ into the project.
python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' "$file" || exit 2
```

### Lint a Dockerfile with hadolint

Useful when editing Compute Environment Dockerfile instructions (see `skills/domino-environments/`).

`.claude/hooks/check-dockerfile.sh`:

```bash
#!/bin/bash
input=$(cat)
file=$(jq -r '.tool_input.file_path // empty' <<<"$input")
case "$(basename "$file")" in Dockerfile|Dockerfile.*|*.Dockerfile) ;; *) exit 0 ;; esac
command -v hadolint >/dev/null || exit 0
hadolint "$file" 1>&2 || exit 2
```

### Format Python with black after a write

`.claude/hooks/format-python.sh`:

```bash
#!/bin/bash
input=$(cat)
file=$(jq -r '.tool_input.file_path // empty' <<<"$input")
[[ "$file" == *.py ]] || exit 0
command -v black >/dev/null || exit 0
black --quiet "$file"
```

### All four together

Handlers in one matcher group run in parallel, so the formatter gets its own group: otherwise
`black` could rewrite the file while the syntax check reads it.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-app-sh.sh" },
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-python.sh" },
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-dockerfile.sh" }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/format-python.sh" }
        ]
      }
    ]
  }
}
```

## Bundling hooks in a plugin

If this plugin ever ships hooks, they go in `hooks/hooks.json`, in the same shape wrapped in a
top-level `"hooks"` key, with scripts referenced through `$CLAUDE_PLUGIN_ROOT`:

```json
{
  "description": "Domino checks",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PLUGIN_ROOT\"/hooks/check-app-sh.sh", "timeout": 30 }
        ]
      }
    ]
  }
}
```

Gemini CLI also loads a `hooks/hooks.json` from an extension directory, in its own format, so a
file by that name here would be read by both hosts. That is one more reason none is shipped.

## Notes

- `/hooks` inside a session lists every configured hook and where it comes from.
- `"disableAllHooks": true` in a settings file turns hooks off without removing them.
- Hooks run with Claude Code's environment from the current directory; keep them fast and make
  them exit 0 when they have nothing to say.
