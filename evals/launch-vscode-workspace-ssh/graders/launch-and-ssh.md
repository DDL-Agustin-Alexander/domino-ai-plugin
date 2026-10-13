---
type: llm
---

PASS if the reply (a) launches the workspace from the project's Workspaces page choosing a compute environment, the VS Code IDE and a GPU hardware tier, and (b) for SSH says to enable SSH access when launching (the "Enable SSH access" setting, with an SSH-capable environment), then connect using the Dom CLI (`dom connect <workspace_id> ...`, which writes an SSH config) together with the VS Code Remote - SSH extension.
FAIL if it offers a python-domino `workspace_start(...)` call, or tells the user to ssh directly to a workspace hostname with a key file without the Dom CLI step.
