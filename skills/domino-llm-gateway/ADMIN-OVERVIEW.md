# LLM Gateway 2.0: what the administrator configures

High-level view for explaining to a user what must be in place before a gateway call works, and for scripting the documented admin queries. Installation, upgrades and day-to-day operation are the administrator's domain and are covered by the material Domino provides with the gateway; the public starting point is https://docs.domino.ai/cloud/platform-capabilities/features/llms/llm-gateway, and access to the gateway itself comes through the Domino field team or account team.

## Deployment shape

- The gateway runs as a **Domino App** in its own Project, owned by a Domino administrator (the owner's rights are what let the gateway see organization memberships and roles). Its URL is the App's URL; everything the UI does is available over HTTP under that base.
- Who administers it: the App owner and Domino administrators, plus any user promoted on the gateway's **Access Policies** > **Gateway Admins** page. Promoted admins can do everything except manage the admin list.
- Who can call it: any authenticated Domino identity that holds an access grant on the alias (or alias group) being called. Viewing the App in Domino and being allowed to call a model are independent settings.

## Providers and aliases

- **Providers** are the upstream connections: OpenAI, Anthropic, Azure OpenAI, AWS Bedrock, Google Vertex AI, generic OpenAI-compatible servers, and the built-in Domino Platform provider for Domino-hosted model endpoints (the `domino-llm-access` skill, Option B). Provider credentials live in the gateway, encrypted, and are never returned to callers.
- **Aliases** are the model catalog: each alias names a provider and an upstream model and is what callers pass as `model`. An alias can carry custom per-million-token prices, an alias-wide budget ceiling, a fallback chain, response caching, and extra headers. **Alias groups** bundle aliases so one grant covers several.
- **Fallback chains**: an alias can list other aliases to retry on timeout, 5xx, 429 or an exhausted budget (each trigger is optional). Links the caller has no grant for are skipped; other 4xx errors (auth, guardrail denials, malformed requests) do not fall back. Fallback happens before the first byte is sent, never mid-stream.

## Access grants and precedence

A grant ties a caller to an alias or alias group and optionally carries a budget. For each request the gateway picks exactly one grant, most specific first:

1. User grant (names the caller)
2. Organization grant (an organization the caller belongs to)
3. Service account grant
4. All-users grant (anyone authenticated)
5. Bring-your-own-token grant (the caller supplied a provider key in `X-LLM-Api-Key`; billed to their own provider account)

The matching grant decides both admission and which budget applies; lower tiers are not consulted once one matches, so a user with a personal grant does not fall through to their organization's pool when the personal budget is spent. Members of several organizations with grants are billed to the grant with the most remaining budget, or to the organization named in `X-LLM-Tag-Bill-Org` when they are a member and it has a grant. Organization membership is cached for a few minutes, so a newly added member may be denied briefly.

## Budgets and cost

- Every request records an **estimated cost** (built-in price book, or the alias's custom input and output rates) attributed to the user and the paying organization; budgets are checked against that running total.
- Two budgets can apply and both must pass: the **alias ceiling** (all traffic through the alias, including BYOT) and the **per-grant budget** on a user, organization or service-account grant. All-users and BYOT grants carry no budget. Periods are daily, weekly or monthly; an empty budget means unlimited, `0` denies everything.
- Enforcement is approximate under heavy concurrency (a small overshoot near the limit is possible), custom prices only re-price prompt and completion tokens, and the estimate uses list rates, so treat the figures as controls rather than invoices.

## Guardrails

Rules screen the request before it leaves the gateway and the response on the way back. A rule has a direction (`input`, `output`, `both`), an action (`deny`, `redact`, `log`), a check (a regex, or an external LLM evaluator endpoint scored against a threshold, configured fail-open or fail-closed), a priority, and an optional alias scope (default: all aliases). Limits to explain to users: output rules on streaming responses can only log; only text is inspected (not images); input scanning sees user-role text, not system prompts or tool results; LLM evaluators add a round-trip per request, so regex rules are preferred for high-volume checks.

## Tokens

Administrators mint **gateway tokens** (`dgw_...`) on the gateway's Tokens page for service accounts, CI and laptops, with an expiry (default 30 days) and revocation. A token carries its owner's identity and organization memberships. Users can also use a Domino Personal Access Token; inside Domino nobody needs either, because the access token from the sidecar is the bearer.

## Usage and audit queries (admin API)

The admin API lives under `<base>/api/` and needs a gateway admin bearer (a gateway token owned by an admin, an admin's PAT, or an admin's in-run access token). It serves the gateway's own UI and is **not versioned between gateway releases**; pin a gateway version before building durable automation on it, and read the live `GET <base>/openapi.json` for exact shapes.

| Need | Route |
|---|---|
| Aggregate requests, tokens, cost, latency, errors, cache hits, guardrail events | `GET /api/usage/stats?range=24h|7d|30d|90d` (`tag_filter=` to slice by attribution tag) |
| Per-request log rows with tokens, `estimated_cost`, `cost_breakdown`, status, latency, fallback and guardrail metadata | `GET /api/usage/logs?limit=&offset=&alias_name=&user_name=&project_name=&status_code=` |
| Cost by alias and by user | `GET /api/usage/cost-breakdown?days=30` |
| Daily rollups and time series | `GET /api/usage/daily?days=`, `GET /api/usage/timeseries?range=&breakdown=` |
| Every enforced budget with current-period spend | `GET /api/usage/budgets`, `.../budgets/{kind}/{ref_id}/series`, `.../activity` |
| Attribution tag keys and values in use | `GET /api/usage/tags`, `GET /api/usage/tags/{key}/values` |
| Audit trail of control-plane changes (providers, aliases, grants, tokens, settings, guardrail events), newest first | `GET /api/audit-logs?limit=&offset=&resource_type=&action=` |
| Catalog reads (any authenticated user) | `GET /api/aliases`, `GET /api/aliases/accessible`, `GET /api/alias-groups` |
| A caller's own usage (any authenticated user) | `GET /api/usage/mine/stats`, `.../mine/logs`, `.../mine/budgets`, `.../mine/cost-breakdown` |

```bash
TOKEN=$(curl -sf "$DOMINO_API_PROXY/access-token")     # in-run; outside Domino use an admin-owned gateway token or PAT
BASE="<base>"

curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/usage/stats?range=30d" | jq
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/usage/cost-breakdown?days=30" | jq
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/usage/logs?limit=200&offset=0" \
  | jq '.logs[] | {alias_name, user_name, tokens_total, estimated_cost, status_code, created_at}'
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/audit-logs?resource_type=access_grant&limit=50" | jq '.logs'
```

Paginated routes take `limit` and `offset` and return `total` with the rows. Usage log rows carry `alias_name`, `provider_model`, `user_name`, `project_name`, `org_name`, prompt, completion and cached token counts, `estimated_cost`, `cost_breakdown`, `latency_ms`, `status_code`, `stream`, `error_message` and a `metadata` object (guardrail actions, fallback details, batch tags). Audit rows carry `action`, `resource_type`, `resource_id`, `resource_name`, `actor_name`, `details` and `created_at`.

Writes (creating providers, aliases, grants, guardrails, tokens, settings) exist on the same API but are the administrator's responsibility; use the gateway UI unless the administrator asks for scripted changes and has pinned the gateway version.
