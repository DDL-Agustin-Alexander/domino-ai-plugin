---
type: llm
---

PASS if the code uses MLflow against Domino's preconfigured tracking server (no custom tracking URI needed), finds the best run with `mlflow.search_runs` or `MlflowClient().search_runs` ordered by `metrics.val_auc`, and registers the model with `mlflow.register_model("runs:/<run_id>/<artifact_path>", "churn-clf")` or `MlflowClient().create_model_version(...)` after creating the registered model.
FAIL if it invents Domino-specific registry functions outside MLflow, or requires an API key.
