---
description: "Negative: a generic Dockerfile request must not load the Domino environments skill."
tags: [negative]
max_turns: 5
allowed_tools: [Read, Glob, Grep, Skill]
---

Write a multi-stage Dockerfile for a Node 20 Express API: install deps with npm ci, copy the source,
run as a non-root user, expose 3000.
