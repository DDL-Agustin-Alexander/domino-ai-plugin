---
description: "Domino CLI: device-code login without a browser, get a DFS project, run with --wait, download-results with --filter."
tags: [trigger, domino-cli, cli]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

I am on a headless Linux server over SSH with no browser. With the Domino command-line client: sign
in to https://domino.example.com, pull my Domino File System project alice/churn, run train.py as a
job with the argument 20 and wait for it, then download only the files under results/ from that run.
Put the code in your reply, not in files.
