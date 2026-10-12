---
type: regex
target: { source: file, path: main.py }
match: not_contains
pattern: '\[\\?[\x27"]iss\\?[\x27"]\]|/auth/realms|\.iss\b'
---
