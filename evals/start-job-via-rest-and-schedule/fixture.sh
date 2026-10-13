#!/usr/bin/env bash
set -euo pipefail
cat > train.py <<'EOF'
import sys
print('epochs', sys.argv[1:])
EOF
