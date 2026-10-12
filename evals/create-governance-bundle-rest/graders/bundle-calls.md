---
type: llm
---

PASS if (a) the bundle is created with `POST .../api/governance/v1/bundles` and a body containing `projectId` (from `DOMINO_PROJECT_ID`), `name` and `policyId`; (b) evidence is attached with `POST .../bundles/{bundleId}/attachments` using an attachment `type` of ModelVersion with an `identifier` naming the registered model and version; (c) findings are read with `GET .../bundles/{bundleId}/findings`; and (d) the base URL and auth follow the in-run rule: `$DOMINO_API_PROXY` with no Authorization header, or the platform host with a bearer from `http://localhost:8899/access-token`, falling back to the public deployment URL with a PAT only if governance returns 404 there.
FAIL if it uses an API key header or derives the host from the JWT `iss` claim.
