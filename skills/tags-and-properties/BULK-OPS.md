# Bulk operations, merging and copying

Routes for bulk lifecycle work on a taxonomy:

- `POST /tags/bulk-delete` and `POST /namespaces/bulk-delete`
- `POST /rpc/merge-tags`: collapse duplicate tags into one
- `POST /rpc/copy-entity-tags` and `POST /rpc/copy-property-values`: copy from one entity to another

All assume `BASE` and `H` from [SKILL.md](./SKILL.md#configuration).

## Bulk delete

```bash
curl -s -X POST -H "$H" -H "Content-Type: application/json" \
  -d '{"ids":["<tag-1>","<tag-2>","<tag-3>"]}' "$BASE/tags/bulk-delete"
# 200 -> {"deletedCount":3}

curl -s -X POST -H "$H" -H "Content-Type: application/json" \
  -d '{"ids":["<ns-1>","<ns-2>"]}' "$BASE/namespaces/bulk-delete"
# 200 -> {"deletedCount":2}
```

Both routes take `{"ids": [...]}` (`ids` required, at least one id) and return
`{"deletedCount": N}`, per both published specs. Deleting tags removes their assignments;
deleting namespaces removes their tags and assignments. There is no undo, so confirm with
the user first and prefer `status: deprecated` on shared deployments.

## Merge tags

```bash
curl -s -X POST -H "$H" -H "Content-Type: application/json" \
  -d '{"sourceTagIds":["<dup-1>","<dup-2>"],"targetTagId":"<canonical>"}' "$BASE/rpc/merge-tags"
# 200 -> {"targetTag":{"id","label","namespace","fullPath"},"mergedCount":2,"reassignedEntities":17}
```

`sourceTagIds` and `targetTagId` are required. Every assignment on the source tags moves
to the target and the source tags are deleted; the docs state merging cannot be undone.

## Copy tags or property values between entities

```bash
curl -s -X POST -H "$H" -H "Content-Type: application/json" \
  -d '{"entityType":"project","sourceEntityId":"<from-id>","targetEntityId":"<to-id>"}' \
  "$BASE/rpc/copy-entity-tags"

curl -s -X POST -H "$H" -H "Content-Type: application/json" \
  -d '{"entityType":"project","sourceEntityId":"<from-id>","targetEntityId":"<to-id>"}' \
  "$BASE/rpc/copy-property-values"
```

All three fields are required; both entities share one `entityType`. Useful when a new
project should start with the same classification as an existing one.

## Patterns

### Bulk-tag during onboarding

Drive `POST /rpc/tag-entity` from a CSV of `entityType,entityId,tagId` rows; there is no
batch tag-entity route.

```bash
while IFS=, read -r etype eid tag; do
  curl -s -X POST -H "$H" -H "Content-Type: application/json" \
    -d "{\"entityType\":\"$etype\",\"entityId\":\"$eid\",\"tagIds\":[\"$tag\"]}" \
    "$BASE/rpc/tag-entity" > /dev/null && echo "tagged $etype/$eid"
done < onboarding.csv
```

For thousands of rows, parallelize with `xargs -P` and refresh the token periodically.

### De-duplicate after free-form tagging

1. `GET $BASE/tags?namespaceId=<id>&limit=200` and group by normalized label.
2. Pick one canonical id per group.
3. `POST $BASE/rpc/merge-tags` per group. Log `mergedCount` and `reassignedEntities`.

### Retire a dimension

Deprecate the namespace (`PUT /namespaces/{id}` with `status: deprecated`) to stop new
assignments while keeping history, or `POST /namespaces/bulk-delete` to remove it and
all assignments.
