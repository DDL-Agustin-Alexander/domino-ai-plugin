# Projects over REST and python-domino

Applies to Domino 6.3 and Domino Cloud. Routes marked (Cloud) exist only in the Cloud spec; everything else is in both `https://docs.domino.ai/api-specs/6.3/public-api.json` and `https://docs.domino.ai/api-specs/cloud/public-api.json`. Read calls were verified against Domino Cloud 6.4 on 2026-10-12. The python-sdk catalog for the same surface is [API-PROJECTS.md](../domino-python-sdk/API-PROJECTS.md).

## Setup

```python
import os
import requests

if os.environ.get("DOMINO_API_PROXY"):                       # inside a Domino run with the proxy
    base, headers = os.environ["DOMINO_API_PROXY"], {}
else:                                                        # run without the proxy: short-lived token
    base = os.environ["DOMINO_API_HOST"]
    token = requests.get("http://localhost:8899/access-token").text.strip()
    headers = {"Authorization": f"Bearer {token}"}
# Outside Domino: base = deployment URL, headers = {"Authorization": "Bearer <PAT or service-account token>"}
```

## Read

| Task | Call |
|------|------|
| List projects you can see | `GET /api/projects/beta/projects?offset=0&limit=10` → `projects[]` (`id`, `name`, `description`, `visibility`, `ownerId`, `ownerUsername`, `collaborators[]`, `isRestricted`), `metadata.totalCount` |
| Get one | `GET /api/projects/v1/projects/{projectId}` → `project` with the same fields; `collaborators[]` entries are `{id, role}` |
| Current project in a run | `$DOMINO_PROJECT_ID` (also `DOMINO_PROJECT_NAME`, `DOMINO_PROJECT_OWNER`) |
| Latest commit (beta) | `GET /api/projects/beta/projects/{projectId}/commits/latest` |
| File content at a commit | `GET /api/projects/v1/projects/{projectId}/files/{commitId}/{path}/content` |
| Imported Git repositories | `GET /api/projects/v1/projects/{projectId}/repositories` |
| Goals | `GET /api/projects/v1/projects/{projectId}/goals` |
| Shared datasets | `GET /api/projects/v1/projects/{projectId}/shared-datasets` |
| Results settings (beta) | `GET` and `PUT /api/projects/beta/projects/{projectId}/results-settings` |

The beta list endpoint takes only `offset` and `limit`; filter by name client-side.

```python
projects, offset = [], 0
while True:
    page = requests.get(f"{base}/api/projects/beta/projects", headers=headers,
                        params={"offset": offset, "limit": 50}).json()
    projects += page["projects"]
    offset += 50
    if offset >= page["metadata"]["totalCount"]:
        break
mine = [p for p in projects if p["name"] == "churn-model"]
```

## Create

`POST /api/projects/v2/projects` (permissions `CreateProject`, `UseFileStorage`). Required: `name` (unique, no whitespace), `description`, `visibility` (`private`, `searchable`; `public` on 6.3 only). The caller owns the project unless `ownerId` names another user (organizations cannot own a project through this route).

DFS project:

```python
r = requests.post(f"{base}/api/projects/v2/projects", headers=headers, json={
    "name": "churn-model", "description": "Churn scoring", "visibility": "private"})
r.raise_for_status()
project_id = r.json()["project"]["id"]
```

Git-based project on an existing repository:

```python
r = requests.post(f"{base}/api/projects/v2/projects", headers=headers, json={
    "name": "churn-model", "description": "Churn scoring", "visibility": "private",
    "mainRepository": {
        "uri": "https://github.com/acme/churn-model.git",
        "serviceProvider": "github",            # bitbucket | bitbucketServer | github | githubEnterprise | gitLab | gitLabEnterprise | unknown
        "gitCredentialId": "<credential id from Account Settings > Git Credentials>",
        "defaultRef": {"refType": "branch", "value": "main"},   # head | branch | tag | commit
    }})
```

Optional: `repoToCreate{credentialId, owner, repositoryToCreateName, visibility, serviceProvider, repositoryTemplateName}` to have Domino create the repository; `templateDetails{templateId, name, templateRevisionId, templateType, importToMainRepo, forceImport}` to start from a project template; `billingTag{tag}`; `isRestricted` (needs `ProjectClassifier`). `POST /api/projects/beta/projects` accepts the same body on the older beta route.

## Collaborators and visibility

```python
requests.post(f"{base}/api/projects/v1/projects/{project_id}/collaborators", headers=headers,
              json={"id": "<user or organization id>", "role": "contributor"})
# roles: contributor | resultsConsumer | launcherUser | projectImporter (the owner role is not assignable)
requests.delete(f"{base}/api/projects/v1/projects/{project_id}/collaborators/<collaboratorId>", headers=headers)
```

Needs `ManageCollaborators`. User ids are the `ownerId` and `collaborators[].id` values returned by the project routes; the users API is in [API-ADMIN.md](../domino-python-sdk/API-ADMIN.md). There is no public route to change visibility after creation; use **Settings** > **Access & Sharing**.

## Copy, status, goals, archive

```python
# Deep copy of a Git-based project into a new repository
# (reference copy instead: "gitCodeRepoSpec": {"credentialId": ..., "referenceCopy": {"mainRepoUrl": "https://github.com/acme/churn-model.git"}})
requests.post(f"{base}/api/projects/v1/projects/{project_id}/copy-project", headers=headers, json={
    "name": "churn-model-v2", "visibility": "private", "copyDatasets": True,
    "gitCodeRepoSpec": {"credentialId": "<PAT credential id>",
                        "deepCopy": {"newRepoName": "churn-model-v2", "newRepoOwnerName": "acme", "visibility": "private"}}})

requests.put(f"{base}/api/projects/v1/projects/{project_id}/status", headers=headers,
             json={"status": "complete", "isBlocked": False, "completedMessage": "Model shipped"})   # or "active"; isBlocked with blockedReason

requests.post(f"{base}/api/projects/v1/projects/{project_id}/goals", headers=headers,
              json={"title": "AUC >= 0.85 on the holdout set", "description": "Q4 target"})
# PATCH .../goals/{goalId}, DELETE .../goals/{goalId}

requests.delete(f"{base}/api/projects/beta/projects/{project_id}", headers=headers)   # archive (ArchiveProject permission)
```

`copyDatasets` is required on copy. Copying a Git-based project needs a personal-access-token credential (not SSH) and, on GitHub, a template repository; a Dataset that is already being copied makes the call fail, so retry later. Only the owner can archive.

## Repositories

```python
requests.post(f"{base}/api/projects/v1/projects/{project_id}/repositories", headers=headers, json={
    "uri": "https://github.com/acme/shared-utils.git", "name": "shared-utils",
    "serviceProvider": "github", "gitCredentialId": "<credential id>",
    "defaultRef": {"refType": "branch", "value": "main"}})     # ChangeProjectSettings permission
requests.delete(f"{base}/api/projects/v1/projects/{project_id}/repositories/<repositoryId>", headers=headers)
```

(Cloud) `PUT /api/projects/v1/projects/{projectId}/repositories/{repositoryId}/default-ref` with `{"refType": "branch", "value": "develop"}` changes what later runs check out; use `_` as the repository id for a Git-based project's main repository. Also (Cloud): `GET .../repositories/{repositoryId}/readme`, `/file-metadata`, `/rendered-file`. Imported repositories mount at `/mnt/imported/code/<name>` (Git-based) or `/repos/<name>` (DFS).

## Shared datasets

`POST /api/projects/v1/projects/{projectId}/shared-datasets` with `{"datasetId": "..."}`; `DELETE .../shared-datasets/{datasetId}`. See `domino-datasets`.

## python-domino

Every method needs a client bound to one project: `Domino("owner/project")`; the `project` argument is required (host from `DOMINO_API_HOST`, auth from the proxy or a token). Methods that exist in `domino/domino.py`:

| Method | Does | Note |
|--------|------|------|
| `project_create(project_name, owner_username=None)` | Creates a DFS project through a legacy route (`POST /project`) | Prefer the REST v2 route above for Git-based projects and templates |
| `projects_list(relationship="Owned", show_completed=False)` | Lists projects | |
| `project_archive(project_name)` | Archives by name | |
| `fork_project(target_name)` | Forks the bound project through the internal `/v4/projects/{id}/fork` route (may change between Domino versions) | Forks are unavailable on Domino Cloud |
| `collaborators_get()`, `collaborators_add(username_or_email, message="")`, `collaborators_remove(username_or_email)` | Collaborators | All three use Domino Internal API routes (may change between Domino versions) |
| `get_user_id(username_or_email)` | Resolves a username or email to a user id (internal `/v4/users` route) | Useful before the public collaborator route above |
| `project_billing_tag(...)`, `project_billing_tag_update(...)`, `project_billing_tag_reset(...)` | Billing tags | |

There is no `project_update`, `project_info` or `project_settings` method; defaults (environment, hardware tier) are set in the UI. Full inventory: [domino-python-sdk](../domino-python-sdk/SKILL.md).
