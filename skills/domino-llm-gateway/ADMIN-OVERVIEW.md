# LLM Gateway 2.0: what the administrator configures

Applies to Domino 6.3 and Domino Cloud where an administrator has deployed LLM Gateway 2.0 (early access; obtained through the Domino field representative, see https://docs.domino.ai/cloud/platform-capabilities/features/llms/llm-gateway).

Everything below happens in the gateway's own UI, by the gateway's owner or an administrator; a developer does not need any of it to call a model, only to understand why a call is refused.

- **Providers and aliases.** The administrator connects upstream providers (external LLM vendors and Domino-hosted model endpoints) and publishes **model aliases**. An alias is the name callers pass as `model`; which vendor model sits behind it is the administrator's choice and can change without callers changing code.
- **Access and budgets.** Access is granted per alias to users, organizations or everyone; a grant can carry a budget for a period, and an alias can carry an overall budget. A call to an alias the caller has no grant for, or whose budget is spent, is refused with a message that says so; the caller asks the administrator for access or budget.
- **Guardrails.** The administrator can screen prompts and responses with rules whose outcome is to deny, redact or log. A denied call returns an error naming the rule; redaction changes the content.
- **Usage and audit.** The gateway records every request (user, Project, alias, tokens, latency, estimated cost) and every configuration change; the administrator reads them in the gateway UI and can attribute spend by the tags callers send (`X-LLM-Tag-<key>` headers).
- **Tokens for use outside Domino.** The administrator can issue gateway tokens (prefix `dgw_`) with an expiry for scripts, CI and laptops; a Domino Personal Access Token works too. Inside Domino nobody needs either: the access token from the sidecar is the bearer.

Installation, upgrades and operation of the gateway are not covered by this skill; point administrators to the material Domino provides with the gateway and to their Domino field representative.
