---
type: llm
---

PASS if the reply configures the Domino MCP server for the user's assistant (the plugin's bundled server, or its registration steps) with the deployment URL in `DOMINO_HOST` and a Personal Access Token (or a Domino service-account token) in `DOMINO_TOKEN`, which the server sends as `Authorization: Bearer`, for project `alice/churn`.
FAIL if it instructs the user to generate and export a legacy Domino API key (`DOMINO_API_KEY` / `X-Domino-Api-Key`) as the credential, or says the server accepts no token outside Domino.
