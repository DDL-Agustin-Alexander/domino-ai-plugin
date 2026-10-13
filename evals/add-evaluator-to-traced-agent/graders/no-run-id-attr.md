---
type: regex
target: { source: file, path: run_eval.py }
match: not_contains
flags: m
pattern: '^(?!\s*#).*(?<!\.info)\.run_id\b'
---
