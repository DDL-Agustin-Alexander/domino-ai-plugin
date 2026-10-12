---
type: llm
focus: { source: file, path: .github/workflows/publish-domino-app.yml }
---

PASS if the workflow reads a Domino Personal Access Token or service-account token from a GitHub secret and sends it as `Authorization: Bearer`, targets the deployment's public URL, and uses `/api/apps/v1/apps/{appId}/...` routes (for example POST `/api/apps/v1/apps/{appId}/versions` or `.../versions/createAndStart`, then a start call) rather than `/api/apps/beta` for the write path.
FAIL if it uses an API key header, relies on `DOMINO_API_PROXY` or `localhost:8899` from GitHub Actions, or leaves the deployment step as a placeholder that prints success without calling the API.
