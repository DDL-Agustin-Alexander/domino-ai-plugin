---
type: llm
---

PASS if the reply configures the Domino MCP server for the user's assistant (the plugin's bundled server or the registration steps) with the deployment URL and project `alice/churn`, and tells the user to authenticate from the laptop with a Personal Access Token (or a Domino service-account token) rather than a legacy API key.
FAIL if it instructs the user to generate and export a legacy Domino API key (`DOMINO_USER_API_KEY` / `X-Domino-Api-Key`) as the recommended credential.
