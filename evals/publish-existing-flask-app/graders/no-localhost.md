---
type: regex
target: { source: file, path: app.sh }
match: not_contains
pattern: '--host[= ]+(localhost|127\.0\.0\.1)|-b\s+(localhost|127\.0\.0\.1)|--bind[= ]+(localhost|127\.0\.0\.1)|host=[\x27"]?(localhost|127\.0\.0\.1)|--port[= ]+5000|-p\s+5000|-l\s+5000|port=5000'
---
