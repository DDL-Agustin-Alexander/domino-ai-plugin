#!/usr/bin/env bash
set -euo pipefail
cat > report.py <<'EOF'
import argparse
p = argparse.ArgumentParser()
p.add_argument('--start-date')
p.add_argument('--end-date')
p.add_argument('--region', default='all')
print(p.parse_args())
EOF
