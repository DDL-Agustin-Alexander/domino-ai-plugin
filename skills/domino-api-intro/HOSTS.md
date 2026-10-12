# Which base URL for which API

Authentication rules: [SKILL.md](./SKILL.md#authentication) and
https://docs.domino.ai/cloud/reference/api/domino-api-authentication.

| Where the code runs | Base URL | Credential |
|---|---|---|
| Inside a Domino execution, `DOMINO_API_PROXY` set | `$DOMINO_API_PROXY` | none (proxy adds the token) |
| Inside a Domino execution, proxy not set | `$DOMINO_API_HOST` | Bearer from `http://localhost:8899/access-token` |
| Outside Domino | The deployment URL (set `DOMINO_API_HOST` to it) | Bearer PAT or service account token |

Do not derive the deployment URL from a JWT claim, and do not copy hostnames out of one
execution into another. Read `DOMINO_API_HOST` or use the URL an API response returns.

## One base for the Public API

Both published specs declare a single server, the deployment hostname. The paths in them
(`/api/...`, `/remotefs/v1`, `/datasetrw/...`, `/model-monitor/...`) are served on that
base, with one documented exception: NetApp file operations under `/remotefs/v1/.../files/*`
take a `/webvfs` prefix outside a run (next section). Inside a run `$DOMINO_API_PROXY` or
`$DOMINO_API_HOST` stands in for the base. Verified on a Domino Cloud deployment with
`GET /api/users/v1/self`, `/api/jobs/beta/jobs`, `/api/taxonomy/v1/config` and
`/remotefs/v1/volumes` on the same base.

## NetApp Volumes (`/remotefs/v1`)

Reference: https://docs.domino.ai/cloud/reference/api/domino-volumes-api (file-operation
hosts are spelled out on the 6.3 page,
https://docs.domino.ai/6.3/reference/api/domino-volumes-api).

| Operation | Inside a run | Outside Domino |
|-----------|--------------|----------------|
| Volume and filesystem CRUD, snapshots, grants, transfers | `$DOMINO_REMOTE_FILE_SYSTEM_HOSTPORT` when Domino injects it, **always with `Authorization: Bearer` from `http://localhost:8899/access-token`** (that host is reached directly, so the API proxy does not add a token); without the variable, the proxy or `$DOMINO_API_HOST` as usual | deployment URL with a PAT or service account token |
| File operations under `/remotefs/v1/volumes/{id}/files/*` and `/remotefs/v1/snapshots/{id}/files/*` | `http://data-webvfs-service.domino-compute:80` with the path as shown in the reference; send the same access-token bearer as for the other remotefs routes (the published spec binds no security scheme to these operations) | deployment URL with `/webvfs` prefixed to the path |

Details: [netapp-volumes](../netapp-volumes/API-NETAPP-VOLUMES.md).

## Model API invocation

Management calls (`/api/modelServing/v1/...`, `/api/registeredmodels/...`) use the Public
API base. Prediction requests go to the Model API's own URL shown on its page in Domino,
with the endpoint's access token, not a platform token:

- Restricted **synchronous** endpoints: HTTP Basic with the access token as both username
  and password.
- Restricted **asynchronous** endpoints (`/api/modelApis/async/v1/{asyncModelId}`):
  `Authorization: Bearer <access token>`.
- Unrestricted endpoints: no token.

Source: https://docs.domino.ai/cloud/platform-capabilities/features/model-deployment/domino-endpoint-authorization.
Workflow: [domino-model-endpoints](../domino-model-endpoints/SKILL.md).

## Governance

Governance routes use the suffix `/api/governance/v1` on the same base. The
[domino-governance](../domino-governance/SKILL.md) skill owns base resolution: try
`$DOMINO_API_PROXY`, then `$DOMINO_API_HOST` with an access token, and on a 404 fall back
to the deployment URL with a PAT or service account token. Use that skill's procedure
rather than restating it.

## API gateway (Domino 6.3 feature flag)

Self-managed Domino 6.3 exposes the feature flag `ShortLived.ApiGateway.UserCodeLocalDpEnabled`
(default `true`). It routes traffic from user workloads on the local data plane through the
Envoy gateway and ext-auth service; `false` reverts to per-service proxy routing in the
execution's nginx sidecar
(https://docs.domino.ai/6.3/admin/configuration/feature-flags). Domino Cloud is operated by
Domino; there is no customer-side switch.

What it means for callers: none of the variable names above change. If an `/api/...` route
returns 404 on `$DOMINO_API_HOST` inside a run, confirm the path against
[API-SPECS.md](./API-SPECS.md), then retry on the deployment URL with a PAT or service
account token.

## Related

- [LIMITS.md](./LIMITS.md) pagination and deprecated credentials
- [ERRORS.md](./ERRORS.md) status codes and retries
- [API-SPECS.md](./API-SPECS.md) OpenAPI files and route discovery
