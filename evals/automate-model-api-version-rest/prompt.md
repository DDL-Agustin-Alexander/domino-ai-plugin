---
description: "Model serving: new model API version via /api/modelServing/v1, polled to Running, with PAT or service-account auth from CI."
tags: [trigger, domino-model-serving, model-deployment]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

From a CI pipeline outside Domino, write a Python requests script that creates a new version of the
existing Domino model API with id 64f0c0ffee from registered model `churn-clf` version 3, then waits
until it is running. REST only. Put the code in your reply, not in files.
