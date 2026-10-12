---
description: "Governance: /api/governance/v1 bundle creation with projectId, name and policyId, attachments and findings, base-URL and auth rules."
tags: [trigger, domino-governance, governance]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

From a Job in my project, use the REST API to create a governance bundle named `churn-model-2026`
for policy id 64a1b2c3d4e5f60718293a4b, attach registered model `churn-clf` version 3 as evidence,
and then list the bundle's findings. Show the calls. Put the code in your reply, not in files.
