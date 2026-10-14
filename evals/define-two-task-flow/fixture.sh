#!/usr/bin/env bash
set -euo pipefail
mkdir -p stages
cat > stages/prep.py <<'EOF'
from pathlib import Path
raw = Path('/workflow/inputs/raw_path').read_text()
Path('/workflow/outputs').mkdir(parents=True, exist_ok=True)
Path('/workflow/outputs/prepared_path').write_text('/mnt/artifacts/prepared.parquet')
EOF
mkdir -p stages
cat > stages/train.py <<'EOF'
from pathlib import Path
p = Path('/workflow/inputs/prepared_path').read_text()
print('training on', p)
EOF
