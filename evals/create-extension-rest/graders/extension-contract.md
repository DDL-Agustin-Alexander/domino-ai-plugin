---
type: llm
---

PASS if the create request is `POST .../api/extensions/beta/extensions` with a body that includes `name`, `enabled`, `appId`, `appVersionId` and `uiMountPointTypeConfigs` (project sidebar mount), the reply notes that only Domino admins can create Extensions and the app must be published with identity propagation, and it says the app receives the originating context as query parameters on its root route (for a project sidebar mount, `projectId`) plus a per-request bearer token in the forwarded headers for calling Domino APIs.
FAIL if it omits `appVersionId` as optional, uses an API key, or says the context is delivered as environment variables.
