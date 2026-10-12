---
description: "an API-policy question (token, header, error handling, paging) loads domino-api-intro, not the Python SDK skill."
tags: [trigger, domino-api-intro, api]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

Policy question, no code: a nightly pipeline outside Domino will call the Domino REST API with plain
HTTP. Which kind of token should it use and in which header, is a user API key acceptable, what
should it do when Domino answers 401, 403 or 502, and how should it read a list of several thousand
jobs without truncation?
