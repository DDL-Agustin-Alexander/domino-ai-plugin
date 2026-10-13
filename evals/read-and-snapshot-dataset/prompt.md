---
description: "Datasets: Git-based mount paths, snapshot via UI or /api/datasetrw/v1 snapshots, snapshot read path; no invented SDK or @tag syntax."
tags: [trigger, domino-datasets, data, disambiguation]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

My Git-based Domino project has a dataset named `sales-raw`. Show the path my job reads it from, how
to take a snapshot after I write processed files into it, and the path to read snapshot number 2
later. Put the code in your reply, not in files.
