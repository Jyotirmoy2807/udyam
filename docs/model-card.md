# Propensity Model Card - Project Udyam Digital

## Model Overview
- **Objective**: Predict activation likelihood (`stage_reached == 'Activated'`) from SME lead attributes.
- **Algorithms**: `LogisticRegression(class_weight="balanced")` & `HistGradientBoostingClassifier`.
- **Target Rate**: ~7.4% baseline activation across 5,000 historical leads.
- **Evaluation Split**: Temporal split (Train: April-May 2026, Test: June 2026).
- **Leakage Prevention**: Strictly zero post-outcome fields used in training.
