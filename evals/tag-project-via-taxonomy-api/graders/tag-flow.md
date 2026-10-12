---
type: llm
---

PASS if the reply (a) resolves the tag to its id first (for example `GET /api/taxonomy/v1/tags/autocomplete?q=clinical` or listing the `domain` namespace's tags), (b) applies it with `POST /api/taxonomy/v1/rpc/tag-entity` and a body with `entityType` `project`, `entityId` `$DOMINO_PROJECT_ID` and `tagIds` as an array of ids, and (c) lists tagged projects with `GET /api/taxonomy/v1/tags/{tagId}/entities` or `GET /api/taxonomy/v1/entities?tagIds=...&entityTypes=project`, using `$DOMINO_API_PROXY` without a header or a bearer token from `http://localhost:8899/access-token`.
FAIL if it tags by label instead of id in the request body, uses an API key, or invents routes outside `/api/taxonomy/v1`.
