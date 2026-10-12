---
type: llm
---

PASS if the reply says the app must bind to 0.0.0.0 and serve on port 8888 (not localhost:5000) and that Domino runs app.sh as the App's entry point / launch file.
FAIL if it says any port is acceptable, or keeps `localhost` / `127.0.0.1` / port 5000 as the configuration to publish.
