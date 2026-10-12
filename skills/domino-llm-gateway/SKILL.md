---
name: domino-llm-gateway
description: Call Large Language Models through Domino LLM Gateway 2.0, the centrally governed gateway an administrator deploys as a Domino App in front of external providers and Domino-hosted models. Covers the gateway base URL, authentication with the in-run access token (fresh per call) or a Personal Access Token or gateway token outside Domino, model aliases and GET /v1/models, the OpenAI-compatible (/v1) and Anthropic-compatible (/anthropic) APIs from the OpenAI and Anthropic SDKs, Pydantic AI, LangChain and plain HTTP, streaming, attribution headers, errors (401, 403, 404, budget exhausted, guardrail denied, fallback), pointing coding assistants (Claude Code, Codex) at the gateway, and what an administrator configures (providers, aliases, grants, budgets, guardrails, usage and audit). Use when a user mentions LLM Gateway, Gateway 2.0, a gateway alias or URL, asks how to call a model through the Domino gateway, how to run Claude Code or Codex through it, why a gateway call was denied, or what the admin must set up.
compatibility: Domino 6.3 and Domino Cloud, only where an administrator has deployed LLM Gateway 2.0 as a Domino App. Inside a Domino execution the bearer is the access token from DOMINO_API_PROXY/access-token (localhost:8899), re-read per call; outside Domino a Personal Access Token or a gateway-issued token. Legacy user API keys are not used.
---

# Domino LLM Gateway 2.0

Applies to Domino 6.3 and Domino Cloud, where an administrator has deployed LLM Gateway 2.0. It is not part of every deployment: Domino distributes it as a Domino App through the field team or account team. If nobody has deployed it, say so and use the `domino-llm-access` skill (provider SDK or a Domino-hosted endpoint); do not try to install it.

## What the gateway is

One base URL in front of many providers (OpenAI, Anthropic, AWS Bedrock, Azure OpenAI, Google Vertex AI, OpenAI-compatible servers, Domino-hosted endpoints). Provider keys stay in the gateway; callers authenticate with their Domino identity. Every request is logged with user, Project, alias, tokens, latency and estimated cost; administrators grant access per **model alias**, set budgets, and screen prompts and responses with guardrails. It replaces the legacy AI Gateway (removed from Cloud, disabled by default on 6.3).

## Base URL

The gateway is a Domino App, so its base is the App's URL as shown on its page in Domino, for example `https://<domino or apps host>/apps/<app id or vanity URL>`. Every API path hangs off that base:

| Family | Path | Use with |
|---|---|---|
| OpenAI-compatible | `<base>/v1` (`/models`, `/chat/completions`, `/embeddings`, `/responses`) | OpenAI SDK, Pydantic AI, LangChain, any OpenAI-style client |
| Anthropic-compatible | `<base>/anthropic` (`/v1/messages`, `/v1/messages/count_tokens`) | Anthropic SDK, Claude Code |

Ask the user for the gateway URL if it is not in a Project environment variable such as `DOMINO_LLM_GATEWAY_URL`. An HTML 404 or "Application not running" page at the base means the App is not deployed or not running; say so instead of retrying.

## Authentication

Send `Authorization: Bearer <token>` on every request; `model` is always an alias name, never a vendor model name.

- **Inside a Domino Workspace, Job or App:** read the access token from `$DOMINO_API_PROXY/access-token` (the sidecar at `http://localhost:8899/access-token`). It expires in minutes, so re-read it before every request instead of caching it in a long-running process.
- **Outside Domino (laptop, CI):** a Domino Personal Access Token, or a gateway token (prefix `dgw_`) an administrator mints in the gateway's Tokens page; both are static, so keep them in an environment variable. An expired gateway token gets `401 Token expired`.
- Legacy user API keys are deprecated and not used. The Anthropic path takes the bearer in `Authorization`, not `x-api-key`.

```python
import os
import requests
from openai import OpenAI

GATEWAY = os.environ["DOMINO_LLM_GATEWAY_URL"].rstrip("/")

def token() -> str:
    proxy = os.environ.get("DOMINO_API_PROXY")
    if proxy:                                         # inside Domino: fresh per call
        return requests.get(f"{proxy}/access-token", timeout=5).text.strip()
    return os.environ["DOMINO_GATEWAY_TOKEN"]        # outside: PAT or dgw_ token

def chat(messages, model="my-gateway-alias", **kwargs) -> str:
    client = OpenAI(base_url=f"{GATEWAY}/v1", api_key=token())
    return client.chat.completions.create(model=model, messages=messages, **kwargs).choices[0].message.content
```

## Discover models

`GET <base>/v1/models` returns the OpenAI list shape (`data[].id`) with the aliases the caller may use; an unknown alias gets `404`.

## Call it

- OpenAI SDK, Responses API, embeddings, Pydantic AI, LangChain, plain HTTP and streaming: [CALLING-MODELS.md](./CALLING-MODELS.md).
- Anthropic SDK: `Anthropic(base_url=f"{GATEWAY}/anthropic", auth_token=token())`, then `client.messages.create(model="<alias>", ...)`.
- Attribution: `X-LLM-Tag-<key>: <value>` headers (for example `X-LLM-Tag-team: research`) slice usage; they are labels, not access control.
- Tracing: OpenAI and Anthropic SDK calls are autologged by `mlflow.openai.autolog()` / `mlflow.anthropic.autolog()`, so the `domino-genai-tracing` skill works unchanged.

## Errors

| Response | Meaning | What to do |
|---|---|---|
| `401` (or an HTML login page) | No bearer, expired access token or gateway token, or the Anthropic path got `x-api-key` | Re-read the access token per call; outside Domino check the PAT or gateway token |
| `403` with a grant or budget message | No access grant on the alias, or the matching user, organization or alias budget for the period is exhausted | Ask the administrator for a grant or budget; the message names which budget ran out |
| `403 Admin access required` | Admin-only route (`<base>/api/...`) | Use `/api/usage/mine/...` for your own usage; the rest needs a gateway admin |
| `404` for a `model` | Not an alias, or the caller cannot see it | `GET /v1/models` and use an exact id |
| `404` HTML at the base URL | App not deployed, not running, or wrong URL | Confirm the App URL with the user or administrator |
| Error naming a guardrail rule | A `deny` rule matched the prompt or response | Change the prompt; `redact` rules rewrite content silently, `log` rules only record |
| `413` from the App proxy | Request body too large | Trim the payload |
| `X-LLM-Fallback-Served-By` header on a 200 | A fallback alias served the request after a timeout, 5xx, 429 or exhausted budget | Expect a different upstream model |

## Coding assistants through the gateway

Claude Code uses the Anthropic path (`ANTHROPIC_BASE_URL=<base>/anthropic` plus an `apiKeyHelper` that re-reads the access token); Codex uses the Responses path (`<base>/v1` with a command-backed bearer). Setup for both, in a Workspace and from a laptop: [CODING-ASSISTANTS.md](./CODING-ASSISTANTS.md).

## What the administrator configures

Providers, aliases and alias groups, access grants (precedence: user, organization, service account, all users, bring-your-own-token), budgets (an alias-wide ceiling plus per-grant budgets; daily, weekly or monthly), guardrails, fallback chains, gateway tokens, and usage and audit queries through the admin API: [ADMIN-OVERVIEW.md](./ADMIN-OVERVIEW.md). Installation and operations are the administrator's domain; point them to the Domino field team or account team.

## Documentation

- LLM Gateway 2.0: https://docs.domino.ai/cloud/platform-capabilities/features/llms/llm-gateway
- Set up LLM access: https://docs.domino.ai/cloud/platform-capabilities/features/llms (6.3: replace `cloud` with `6.3`)
- Coding assistants and the gateway: https://docs.domino.ai/cloud/platform-capabilities/features/coding-assistants/reuse-credentials#use-with-domino-llm-gateway-2-0
- API authentication: https://docs.domino.ai/cloud/reference/api/domino-api-authentication
