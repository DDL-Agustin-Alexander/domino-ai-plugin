#!/usr/bin/env bash
set -euo pipefail
: > model.pkl
cat > train.py <<'EOF'
import pickle
from sklearn.linear_model import LogisticRegression
from sklearn.datasets import load_iris
X, y = load_iris(return_X_y=True)
pickle.dump(LogisticRegression(max_iter=200).fit(X, y), open('model.pkl', 'wb'))
EOF
