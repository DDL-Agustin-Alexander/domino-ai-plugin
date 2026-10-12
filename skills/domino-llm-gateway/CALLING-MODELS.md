# Calling models through LLM Gateway 2.0

Applies to Domino 6.3 and Domino Cloud where an administrator has deployed LLM Gateway 2.0 as a Domino App. All examples use:

- `GATEWAY`: the App's URL without a trailing slash (`https://<domino or apps host>/apps/<app id or vanity URL>`), kept in a Domino environment variable such as `DOMINO_LLM_GATEWAY_URL`.
- `token()`: the bearer. Inside a Domino execution it is the access token from `$DOMINO_API_PROXY/access-token` (`http://localhost:8899/access-token`), re-read before every request because it expires in minutes; outside Domino a Personal Access Token or a gateway token (`dgw_...`) from an environment variable. Never a legacy user API key.
- `model`: a gateway **alias** name, never a vendor model name. List them with `GET {GATEWAY}/v1/models`.

```python
import os
import requests

GATEWAY = os.environ["DOMINO_LLM_GATEWAY_URL"].rstrip("/")

def token() -> str:
    proxy = os.environ.get("DOMINO_API_PROXY")
    if proxy:
        return requests.get(f"{proxy}/access-token", timeout=5).text.strip()
    return os.environ["DOMINO_GATEWAY_TOKEN"]
```

Build the client right before the call (or refresh its key) so a long-running Job or App never sends an expired token. Constructing an OpenAI client is cheap.

## List the aliases you can use

```python
r = requests.get(f"{GATEWAY}/v1/models", headers={"Authorization": f"Bearer {token()}"}, timeout=10)
r.raise_for_status()
for m in r.json()["data"]:          # OpenAI list shape: {"object": "list", "data": [{"id": ..., "owned_by": ...}]}
    print(m["id"])
```

`GET {GATEWAY}/v1/whoami` shows how the gateway resolved your identity (user, organizations), which is the first thing to check when a grant does not seem to apply.

## OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url=f"{GATEWAY}/v1", api_key=token())
response = client.chat.completions.create(
    model="my-gateway-alias",
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.2,
    max_tokens=512,
    extra_headers={"X-LLM-Tag-team": "research"},   # optional attribution tag
)
print(response.choices[0].message.content)
```

Tool calling, JSON mode and the other chat-completions parameters pass through; whether the upstream model honours one is the model's business. The Responses API is served at `{GATEWAY}/v1/responses` (`client.responses.create(model="my-gateway-alias", input="Hello")`) and embeddings at `{GATEWAY}/v1/embeddings` (`client.embeddings.create(model="<embedding alias>", input=[...])`).

## Anthropic SDK

The Anthropic-compatible path is `{GATEWAY}/anthropic`. Pass the bearer as `auth_token` (sent as `Authorization: Bearer`); `api_key` would be sent as `x-api-key`, which the gateway ignores, and you get a 401.

```python
from anthropic import Anthropic

client = Anthropic(base_url=f"{GATEWAY}/anthropic", auth_token=token())
message = client.messages.create(
    model="my-gateway-alias",
    max_tokens=512,
    messages=[{"role": "user", "content": "Hello"}],
)
print(message.content[0].text)
```

Aliases that point at an Anthropic-family model (served by Anthropic, Bedrock or Vertex) are forwarded natively, so `cache_control`, extended thinking and native tool-use blocks survive. Aliases that point at any other provider are translated to the OpenAI chat format and back; tool use and vision still work, while `cache_control` markers, thinking budgets and `anthropic-beta` / `anthropic-version` headers are dropped. The Python Anthropic SDK does not read `ANTHROPIC_CUSTOM_HEADERS`; pass attribution tags with `default_headers={"X-LLM-Tag-team": "research"}`.

## Pydantic AI

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

model = OpenAIChatModel(
    "my-gateway-alias",
    provider=OpenAIProvider(base_url=f"{GATEWAY}/v1", api_key=token()),
)
agent = Agent(model)
print(agent.run_sync("Hello").output)
```

Rebuild the provider (or the agent) per batch of calls in a long-running process so the token stays fresh.

## LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="my-gateway-alias", base_url=f"{GATEWAY}/v1", api_key=token())
print(llm.invoke("What is machine learning?").content)
```

## Plain HTTP

```python
r = requests.post(
    f"{GATEWAY}/v1/chat/completions",
    headers={"Authorization": f"Bearer {token()}", "X-LLM-Tag-team": "research"},
    json={"model": "my-gateway-alias", "messages": [{"role": "user", "content": "Hello"}]},
    timeout=120,
)
r.raise_for_status()
print(r.json()["choices"][0]["message"]["content"])
```

## Streaming

```python
client = OpenAI(base_url=f"{GATEWAY}/v1", api_key=token())
with client.chat.completions.stream(model="my-gateway-alias",
                                    messages=[{"role": "user", "content": "Write a haiku about the Alps"}]) as stream:
    for event in stream:
        if event.type == "content.delta":
            print(event.delta, end="", flush=True)
```

Or `stream=True` on `chat.completions.create` and read `chunk.choices[0].delta.content`. Streaming works through the Domino App proxy for continuous streams; a long silent gap (for example extended thinking) is the first suspect if a stream hangs. Output guardrails on a streaming response can only log, not deny or redact, because chunks are already delivered.

## Attribution headers

| Header | Effect |
|---|---|
| `X-LLM-Tag-<key>: <value>` | Caller-defined tag stored on the usage log row and filterable in the Usage dashboard (up to 20 per request). Attribution only; never rely on it for access control. |
| `X-LLM-Tag-Bill-Org: <org id>` | For members of several organizations: bill this request against that organization's grant and budget (ignored unless you are a member and it has a grant). |
| `X-LLM-Api-Key: <provider key>` | Bring your own provider key; needs a BYOT grant on the alias, and the call is billed to your provider account. |

## Errors to expect

- `401`: missing or expired bearer; an HTML login page instead of JSON means the request reached the App proxy without a bearer. Re-read the access token per call.
- `403` with a message about a grant or budget: no grant on the alias, or the matching budget (your user grant, your organization's grant, or the alias ceiling) is exhausted for its period; the message names which. Budgets do not fall through from a user grant to an organization grant.
- `403 Admin access required`: an admin-only route under `{GATEWAY}/api/`.
- `404` on `model`: not an alias you can see. `404` HTML from the base URL: the App is not deployed or not running.
- A guardrail `deny` rule returns an error naming the rule; `redact` rules rewrite the content without an error.
- `413` from the App proxy: the request body is too large (tens of megabytes; usually a huge tool result).
- `429` or `5xx` from the upstream provider may be retried by the gateway against the alias's fallback chain; a fallback-served reply carries `X-LLM-Fallback-Reason` and `X-LLM-Fallback-Served-By` headers.

## Batch requests

If the administrator has enabled batch processing, the gateway also serves the OpenAI batch endpoints (`POST /v1/files`, `POST /v1/batches`, `GET /v1/batches/{id}`, `GET /v1/files/{id}/content`) and the Anthropic message-batch endpoints under `/anthropic/v1/messages/batches`, with the same grants, budgets and guardrails. Use a gateway token or PAT for batches, since they outlive an access token; every line's `model` must be the same alias; and read both the output file and the error file, because failed lines are reported in the error file by `custom_id`. When batch processing is off, these routes return 404.

## Tracing gateway calls

Gateway calls made with the OpenAI or Anthropic SDK are ordinary SDK calls, so MLflow autologging and the Domino agents SDK capture them with no gateway-specific work:

```python
import mlflow
mlflow.openai.autolog()        # or mlflow.anthropic.autolog()
```

See the `domino-genai-tracing` skill. The gateway's own usage log (tokens, latency, estimated cost per request) is separate and lives in the gateway UI.

## Your own usage

Any authenticated caller can read their own usage without admin rights: `GET {GATEWAY}/api/usage/mine/stats`, `.../mine/logs`, `.../mine/budgets` (same shapes as the admin routes, scoped to you). The admin API is not versioned between gateway releases, so treat these shapes as informational.
