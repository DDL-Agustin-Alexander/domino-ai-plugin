---
type: regex
target: { source: file, path: qa.py }
match: not_contains
pattern: '(?<!\.info)\.run_id\b'
---
