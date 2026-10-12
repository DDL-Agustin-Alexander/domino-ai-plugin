---
type: regex
target: { source: file, path: app.sh }
match: not_contains
pattern: 'localhost|127\.0\.0\.1|5000'
---
