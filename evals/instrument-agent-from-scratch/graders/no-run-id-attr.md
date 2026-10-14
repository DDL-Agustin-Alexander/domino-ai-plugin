---
type: regex
target: { source: file, path: qa.py }
match: not_contains
flags: m
pattern: '^(?!\s*#).*(?<!\.info)\.run_id\b'
---
