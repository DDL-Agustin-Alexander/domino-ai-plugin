# Domino Environments API

Create, revise and inspect Compute Environments. Routes and fields are from both
published specs unless marked **Cloud**. Product docs:
https://docs.domino.ai/cloud/platform-capabilities/core-concepts/compute-environments.

## Authentication

Use the shared setup block (`base_url`, `headers`) from
[domino-api-intro](../domino-api-intro/SKILL.md#authentication).

## List environments

```
GET /api/environments/beta/environments?offset=0&limit=50
```

Only `offset` and `limit`. Response: `{"environments": [...], "metadata": {...}}`. Each
environment has `id`, `name`, `visibility` (`global`, `private`, `organization`),
`owner` (`id`, `username`, `ownerType`), `supportedClusters`, `archived`, `isCurated`,
`rebuildOnBaseChanges` and `latestRevision` (`id`, `number`, `status`, `availableTools`,
`architectures`).

```python
envs = requests.get(f"{base_url}/api/environments/beta/environments", headers=headers,
                    params={"limit": 100}).json()["environments"]
for env in envs:
    print(env["name"], env["id"], env["latestRevision"]["status"])
```

## Create an environment

```
POST /api/environments/beta/environments
```

No field is marked required in the spec; send at least `name`, `visibility` (`global` or
`private`) and build inputs. Build fields: `image` (base image), `dockerfileInstructions`,
`preSetupScript`, `postSetupScript`, `preRunScript`, `postRunScript`,
`environmentVariables` (`[{"key", "value"}]`), `workspaceTools`, `supportedClusters`
(`dask`, `mpi`, `ray`, `slurm`, `spark`), `skipCache`, `summary`, `useVpn`,
`addBaseDependencies`, `duplicateFromEnvironmentId`, `isRestricted`, `isCurated`,
`orgOwnerId`, `rebuildOnBaseChanges` (`never`, `followActive`). There is no
`baseEnvironmentId`; base on another Domino environment with `duplicateFromEnvironmentId`
or on an image with `image`.

```python
env = requests.post(f"{base_url}/api/environments/beta/environments", headers=headers, json={
    "name": "pytorch-gpu-env",
    "visibility": "private",
    "duplicateFromEnvironmentId": "<domino-standard-environment-id>",
    "dockerfileInstructions": "RUN pip install --no-cache-dir torch==2.4.0 torchvision==0.19.0",
    "summary": "PyTorch with GPU support",
}).json()
```

**Cloud only:** `POST /api/environments/v2/environments` takes `initialRevision`
(`buildConfiguration`, `architectures` `amd64`/`arm64`, `environmentVariables`) and
`duplicateFromEnvironmentId`; `PUT .../v1/environments/{environmentId}/name` and
`/description` rename.

## Get an environment

```
GET /api/environments/v1/environments/{environmentId}
```

Returns `{"environment": {...}, "metadata": {...}}` with the fields listed under List.

## Archive an environment

```
DELETE /api/environments/v1/environments/{environmentId}
```

## Revisions

```
POST  /api/environments/beta/environments/{environmentId}/revisions
PATCH /api/environments/beta/environments/{environmentId}/revisions/{revisionId}   body: {"isRestricted": true}
```

Revision body: the same build fields as create (`image`, `dockerfileInstructions`,
scripts, `environmentVariables`, `workspaceTools`, `supportedClusters`, `skipCache`,
`summary`, `useVpn`). `isRestricted` is required on PATCH.

```python
rev = requests.post(f"{base_url}/api/environments/beta/environments/{env_id}/revisions",
                    headers=headers, json={
    "dockerfileInstructions": "RUN pip install --no-cache-dir pandas==2.2.2 scikit-learn==1.5.1",
    "summary": "pin pandas and scikit-learn",
}).json()
```

## Build status

Poll `GET /api/environments/v1/environments/{environmentId}` and read
`environment.latestRevision.status`. Values (`EnvironmentRevisionBuildStatusV1`):
`queued`, `starting`, `pulling`, `building`, `pushing`, `succeeded`, `failed`, `killed`.

```python
import time
while True:
    env = requests.get(f"{base_url}/api/environments/v1/environments/{env_id}",
                       headers=headers).json()["environment"]
    status = env["latestRevision"]["status"]
    if status in ("succeeded", "failed", "killed"):
        break
    print("building...", status)
    time.sleep(30)
```

## Use the environment in a job

```python
requests.post(f"{base_url}/api/jobs/v1/jobs", headers=headers, json={
    "projectId": project_id,
    "runCommand": "python train.py",
    "environmentId": env_id,
    "hardwareTier": "small-k8s",
})
```

Body reference: [API-JOBS.md](./API-JOBS.md#start-a-job).

## Dockerfile instructions

`dockerfileInstructions` is a Dockerfile fragment appended to the base image. Domino
images run as the `ubuntu` user; do not add a `USER` line. Guidance:
https://docs.domino.ai/cloud/platform-capabilities/core-concepts/compute-environments/manage-compute-environments.

```dockerfile
RUN pip install --no-cache-dir pandas==2.2.2 numpy>=1.26 scikit-learn==1.5.1
RUN apt-get update && apt-get install -y libpq-dev graphviz && rm -rf /var/lib/apt/lists/*
RUN R -e "install.packages(c('tidyverse', 'caret'), repos='https://cloud.r-project.org')"
ENV MODEL_PATH=/mnt/artifacts/model.pkl
```

## python-domino

`environments_list()`, `get_environment(environment_id)`, `get_default_environment()`,
`create_environment(name, visibility, ...)`, `create_environment_revision(environment_id, ...)`,
`restrict_environment_revision(environment_id, revision_id)`, `archive_environment(environment_id)`.
`get_environment`, `create_environment` and `create_environment_revision` call the Public
API routes above. Signatures: [SDK-EXAMPLES.md](./SDK-EXAMPLES.md#environments-and-hardware-tiers).
There is no `environment_get` method.

## Best practices

1. Start from a Domino Standard Environment (`duplicateFromEnvironmentId`).
2. Pin package versions.
3. Combine `RUN` lines to reduce layers and clean package caches.
4. Create a revision rather than a new environment for dependency changes; Workspaces and
   Jobs pick the active revision.
