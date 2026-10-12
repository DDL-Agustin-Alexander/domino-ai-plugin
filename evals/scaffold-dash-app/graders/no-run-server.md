---
type: regex
target: { source: file, path: app.py }
match: not_contains
flags: m
pattern: '^(?!\s*#).*\.run_server\('
---
