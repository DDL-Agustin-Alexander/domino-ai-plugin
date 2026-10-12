# SDK and skill map

Where to go after [SKILL.md](./SKILL.md). Product doc links use https://docs.domino.ai/...

## API surface to skill

All Public API families below are served on the same base URL: `$DOMINO_API_PROXY` or
`$DOMINO_API_HOST` inside a run, the deployment URL outside ([HOSTS.md](./HOSTS.md)).

| Surface | Routes | Plugin skill / reference |
|---------|--------|---------------------------|
| REST overview and python-domino | `/api/...` | [domino-python-sdk](../domino-python-sdk/SKILL.md), [API-REFERENCE](../domino-python-sdk/API-REFERENCE.md) |
| Jobs | `/api/jobs/v1`, `/api/jobs/beta` | [domino-jobs](../domino-jobs/SKILL.md), [API-JOBS](../domino-python-sdk/API-JOBS.md) |
| Projects, collaborators, git repos, goals | `/api/projects/v1`, `/api/projects/beta`, `/api/projects/v2` | [domino-projects](../domino-projects/SKILL.md), [API-PROJECTS](../domino-python-sdk/API-PROJECTS.md) |
| Datasets and snapshots | `/api/datasetrw/v1`, `/api/datasetrw/v2` | [domino-datasets](../domino-datasets/SKILL.md), [API-DATASETS](../domino-python-sdk/API-DATASETS.md) |
| Data sources and their audit | `/api/datasource/v1` | [domino-data-connectivity](../domino-data-connectivity/SKILL.md), [API-ADMIN](../domino-python-sdk/API-ADMIN.md) |
| Data access from code (SQL, object storage, dataset files) | Domino Data API (`dominodatalab-data`) | [domino-data-sdk](../domino-data-sdk/SKILL.md) |
| NetApp Volumes | `/remotefs/v1` | [netapp-volumes](../netapp-volumes/SKILL.md) |
| Tags and properties | `/api/taxonomy/v1` | [tags-and-properties](../tags-and-properties/SKILL.md) |
| Apps | `/api/apps/v1`, `/api/apps/beta` | [domino-apps](../domino-apps/SKILL.md), [API-APPS](../domino-apps/API-APPS.md) |
| Model APIs, deployments, registry | `/api/modelServing/v1`, `/api/registeredmodels/v1`, `/v2` | [domino-model-serving](../domino-model-serving/SKILL.md), [domino-model-endpoints](../domino-model-endpoints/SKILL.md), [API-MODELS](../domino-python-sdk/API-MODELS.md) |
| Governance | `/api/governance/v1` | [domino-governance](../domino-governance/SKILL.md) |
| Extensions | `/api/extensions/beta` | [domino-extensions](../domino-extensions/SKILL.md) |
| Workspaces | `/api/projects/v1/.../workspaces/{id}/sessions`; `/api/workspace/v1` (Cloud only) | [domino-workspaces](../domino-workspaces/SKILL.md) |
| Environments | `/api/environments/beta`, `/v1`, `/v2` (Cloud) | [domino-environments](../domino-environments/SKILL.md), [API-ENVIRONMENTS](../domino-python-sdk/API-ENVIRONMENTS.md) |
| Users, orgs, service accounts, PATs, hardware tiers, cost, audit trail | `/api/users/v1`, `/api/organizations/v1`, `/api/serviceAccounts/v1`, `/api/pat/v1`, `/api/hardwaretiers/v1`, `/api/cost/v1`, `/api/audittrail/v1` | [API-ADMIN](../domino-python-sdk/API-ADMIN.md) |

## LLM access

Calling external LLM providers through Domino is covered by the `domino-llm-access`
skill (shipped as `domino-ai-gateway` until that rename lands in this release). On
Domino 6.3 the AI Gateway routes (`/api/aigateway/v1/*`) exist in the 6.3 spec; Domino
Cloud has removed them, so nothing under `/api/aigateway` is callable there.

GenAI endpoint management (`/api/gen-ai/beta/endpoints`) is in both specs; see
[domino-model-endpoints](../domino-model-endpoints/SKILL.md).

## Discovery for agents

| Resource | Purpose |
|----------|---------|
| https://docs.domino.ai/llms.txt | Index of every docs page (append `.md` to read one) |
| https://docs.domino.ai/llms-full.txt | Expanded index with page summaries |
| [API-SPECS.md](./API-SPECS.md) | OpenAPI files, published and per deployment |
