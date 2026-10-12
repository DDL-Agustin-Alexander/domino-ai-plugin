---
type: regex
target: { source: file, path: flow.py }
match: not_contains
pattern: '@task\(|@task\s'
---
