---
description: "NetApp volumes: DFS mount paths incl. numbered snapshots, and POST /remotefs/v1/snapshots with volumeId and description."
tags: [trigger, netapp-volumes, data, disambiguation]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

We attached a NetApp volume named `genomics` to my DFS-based Domino project. Where is it mounted in
a workspace, where do I read snapshot number 3, and how do I create a snapshot with a message from a
script using the API? Put the code in your reply, not in files.
