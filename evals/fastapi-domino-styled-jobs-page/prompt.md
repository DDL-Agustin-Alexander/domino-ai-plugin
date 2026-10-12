---
description: "UI design: Domino-styled FastAPI app (main.py, app.sh) that authenticates through the proxy or access-token endpoint, uses relative URLs, serves on 0.0.0.0:8888."
tags: [trigger, domino-ui-design, apps]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

Build a small FastAPI web page that lists the jobs in my Domino project and looks like the Domino UI
(Domino design system). Write the backend to main.py and the launch script to app.sh, and explain
how it calls the Domino API and why it is served the way it is so it works as a Domino App.
