---
description: "Disambiguation: app CI/CD loads domino-apps and automates with /api/apps/v1 and a PAT or service-account secret."
tags: [trigger, domino-apps, apps, disambiguation]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

Write a GitHub Actions workflow to .github/workflows/publish-domino-app.yml that publishes a new
version of my existing Domino App (app id 68b1c2d3e4f5a6b7c8d9e0f1) on every push to main, using the
Domino REST API.
