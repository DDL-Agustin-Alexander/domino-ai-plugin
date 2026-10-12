# Domino Projects API

Create and manage projects, collaborators, git repositories, goals and shared datasets.
All routes and bodies below are in both published specs unless marked **Cloud**.
Product docs: https://docs.domino.ai/cloud/platform-capabilities/core-concepts/projects.

## Authentication

Use the shared setup block (`base_url`, `headers`) from
[domino-api-intro](../domino-api-intro/SKILL.md#authentication).

## List projects

```
GET /api/projects/beta/projects?offset=0&limit=20
```

Only `offset` and `limit` are accepted; there is no name or owner filter, so filter
client-side. Response: `{"projects": [...], "metadata": {"offset", "limit", "totalCount", "notices", "requestId"}}`.
Each project has `id`, `name`, `description`, `visibility` (`Private`, `Searchable`,
`Public`), `ownerId`, `ownerUsername`, `collaborators`, `isRestricted`, optional
`billingTag`.

```python
projects = requests.get(f"{base_url}/api/projects/beta/projects", headers=headers,
                        params={"limit": 50}).json()["projects"]
mine = [p for p in projects if p["name"] == "fraud-detection"]
```

## Create a project

```
POST /api/projects/beta/projects      (also POST /api/projects/v2/projects, same body)
```

Required: `name`, `description`, `visibility` (`public`, `searchable`, `private`).
Optional: `ownerId`, `isRestricted`, `billingTag` (`{"tag": "..."}`), `mainRepository`
(`uri` required; `name`, `serviceProvider`, `gitCredentialId`, `defaultRef`
`{"refType": "head|branch|tag|commit", "value": "..."}`) to make a Git-based project,
`repoToCreate`, `templateDetails` (`name`, `templateId` required).

```python
project = requests.post(f"{base_url}/api/projects/beta/projects", headers=headers, json={
    "name": "fraud-detection",
    "description": "Fraud detection model",
    "visibility": "private",
}).json()
project_id = project["project"]["id"] if "project" in project else project["id"]
```

Read the response shape once on your deployment; beta routes may wrap the object.

## Get a project

```
GET /api/projects/v1/projects/{projectId}
```

Returns `{"project": {...}, "metadata": {...}}`.

## Archive a project

```
DELETE /api/projects/beta/projects/{projectId}
```

## Copy a project

```
POST /api/projects/v1/projects/{projectId}/copy-project
```

Required: `copyDatasets` (boolean). Optional: `name`, `ownerId`, `visibility`,
`billingTag`, `copyNetAppVolumes`, `importedGitReposCredentialId`, `gitCodeRepoSpec`
(`credentialId` required, plus one of `referenceCopy`, `deepCopy`, `importFilesTarget`).

## Project status

```
PUT /api/projects/v1/projects/{projectId}/status
```

Body: `{"status": "active" | "complete", "isBlocked": false, "blockedReason": "...", "completedMessage": "..."}`;
`status` and `isBlocked` are required.

## Collaborators

```
POST   /api/projects/v1/projects/{projectId}/collaborators
DELETE /api/projects/v1/projects/{projectId}/collaborators/{collaboratorId}
```

Body: `{"id": "<user-id>", "role": "contributor"}`. `role` is one of `contributor`,
`launcherUser`, `resultsConsumer`, `projectImporter` (owner is not assignable here). Find
user ids with `GET /api/users/v1/users`.

```python
requests.post(f"{base_url}/api/projects/v1/projects/{project_id}/collaborators",
              headers=headers, json={"id": user_id, "role": "contributor"})
```

There is no Public API route that lists collaborators separately; the project object from
`GET /api/projects/v1/projects/{projectId}` carries `collaborators`.

## Git repositories

```
GET    /api/projects/v1/projects/{projectId}/repositories
POST   /api/projects/v1/projects/{projectId}/repositories
DELETE /api/projects/v1/projects/{projectId}/repositories/{repositoryId}
```

Create body: `uri` required; optional `name`, `serviceProvider` (`github`,
`githubEnterprise`, `gitLab`, `gitLabEnterprise`, `bitbucket`, `bitbucketServer`,
`unknown`), `gitCredentialId`, `defaultRef` `{"refType": "head|branch|tag|commit", "value": "main"}`.

```python
requests.post(f"{base_url}/api/projects/v1/projects/{project_id}/repositories", headers=headers, json={
    "uri": "https://github.com/org/repo.git",
    "name": "repo",
    "serviceProvider": "github",
    "defaultRef": {"refType": "branch", "value": "main"},
    "gitCredentialId": "<credential-id>",
})
```

**Cloud only:** `PUT .../repositories/{repositoryId}/default-ref`, `GET .../file-metadata`,
`GET .../readme`, `GET .../rendered-file`.

## Project goals

```
GET    /api/projects/v1/projects/{projectId}/goals
POST   /api/projects/v1/projects/{projectId}/goals          body: {"title": "...", "assigneeId": "...", "stageId": "..."}
PATCH  /api/projects/v1/projects/{projectId}/goals/{goalId} body: {"isComplete": true}
DELETE /api/projects/v1/projects/{projectId}/goals/{goalId}
```

`title` is required on create; `isComplete` is required on update. Link a job to a goal
with `POST /api/jobs/v1/goals?jobId=...` ([API-JOBS.md](./API-JOBS.md#job-goals)).

## Shared datasets

```
GET    /api/projects/v1/projects/{projectId}/shared-datasets
POST   /api/projects/v1/projects/{projectId}/shared-datasets      body: {"datasetId": "<dataset-id>"}
DELETE /api/projects/v1/projects/{projectId}/shared-datasets/{datasetId}
```

## Project files

```
GET /api/projects/v1/projects/{projectId}/files/{commitId}/{path}/content
GET /api/projects/beta/projects/{projectId}/commits/latest
POST /api/projects/beta/projects/{projectId}/commits/resolveGitRef
```

```python
commit = requests.get(f"{base_url}/api/projects/beta/projects/{project_id}/commits/latest",
                      headers=headers).json()
content = requests.get(
    f"{base_url}/api/projects/v1/projects/{project_id}/files/{commit_id}/train.py/content",
    headers=headers).text
```

## Results settings

```
GET /api/projects/beta/projects/{projectId}/results-settings
PUT /api/projects/beta/projects/{projectId}/results-settings      body: {"branch": "main"}
```

## Project settings and defaults

The Public API has no route for project settings (default hardware tier, environment).
On Domino Cloud, `POST /api/jobs/v1/projects/{projectId}/job-defaults` resolves the
defaults a job would use ([API-JOBS.md](./API-JOBS.md#job-defaults-domino-cloud-only)).
`GET /v4/projects/{projectId}/settings` returns them on both targets but is Domino Internal
API, may change between Domino versions; confirm it in your deployment's
`/docs/openapi/openapi-internal.json` before relying on it.

## python-domino

`project_create(project_name, owner_username=None)`, `project_create_v4(...)`,
`projects_list(relationship="Owned", show_completed=False)`, `project_archive(project_name)`,
`fork_project(target_name)`, `collaborators_get()`, `collaborators_add(username_or_email)`,
`collaborators_remove(username_or_email)` and the `project_id` property. Signatures and
notes: [SDK-EXAMPLES.md](./SDK-EXAMPLES.md#projects-collaborators-project-tags). There is
no `project_info`, `project_get` or `project_update`.
