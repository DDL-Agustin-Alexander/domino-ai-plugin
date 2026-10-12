---
description: "Disambiguation: a deep-link 404 on a published Vite app loads domino-debug-proxy and finds the missing SPA fallback."
tags: [trigger, domino-debug-proxy, apps, disambiguation]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

My published Vite + React app on Domino loads fine on its home route, but refreshing the browser on
/reports returns a 404 from the app. Look at the config here and tell me what is wrong. Do not edit
anything yet.
