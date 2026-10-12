---
description: "API intro: auth inside a run uses DOMINO_API_PROXY or the local access-token endpoint; outside a run a PAT or service-account bearer; never API keys."
tags: [trigger, domino-api-intro, api]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

I am writing one Python script that calls the Domino REST API. It will run inside a Domino Job and
also from a CI pipeline outside Domino. How should it authenticate in each case? Show the code for
both. Put the code in your reply, not in files.
