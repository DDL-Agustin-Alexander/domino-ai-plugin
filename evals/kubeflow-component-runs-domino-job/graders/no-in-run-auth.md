---
type: regex
target: last_message
match: not_contains
pattern: '\$\{?DOMINO_API_PROXY\}?/|environ(\.get)?\(\s*[\x27"]DOMINO_API_PROXY|environ\[\s*[\x27"]DOMINO_API_PROXY|getenv\(\s*[\x27"]DOMINO_API_PROXY|[\x27"]https?://localhost:8899|curl[^\n]*localhost:8899'
---
