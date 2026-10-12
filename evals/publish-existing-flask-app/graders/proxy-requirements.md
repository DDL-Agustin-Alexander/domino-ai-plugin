---
type: llm
---

PASS if the reply says the app must listen on 0.0.0.0 and port 8888 for Domino's proxy to reach it (so the laptop's 127.0.0.1:5000 setting cannot be used as is), and treats app.sh as the script Domino executes to start the App when it is published (describing what app.sh runs is enough).
FAIL if it says any port is acceptable, or keeps `localhost` / `127.0.0.1` / port 5000 as the configuration to publish.
