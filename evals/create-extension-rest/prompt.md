---
description: "Extensions: POST /api/extensions/beta/extensions with name, enabled, appId, appVersionId and uiMountPointTypeConfigs; admins only; context arrives as query params."
tags: [trigger, domino-extensions, extensions]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

I have a published Flask app (app id 68a0b1c2d3e4f5a6b7c8d9e0, version id 68a0b1c2d3e4f5a6b7c8d9e1)
with identity propagation enabled. Create a Domino Extension that shows it in the project sidebar
using the REST API, and tell me what my app receives when someone opens it from a project. Put the
code in your reply, not in files.
