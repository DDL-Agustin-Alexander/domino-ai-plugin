#!/usr/bin/env bash
set -euo pipefail
cat > requirements.txt <<'EOF'
scikit-learn
mlflow
EOF
cat > train.py <<'EOF'
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
X, y = load_iris(return_X_y=True)
print(RandomForestClassifier().fit(X, y).score(X, y))
EOF
