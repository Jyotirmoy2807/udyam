# Model Card: Lead Propensity Scoring Model

## Model Details
- **Model Name**: Accel SMB Lead Conversion Propensity Model
- **Version**: 1.0.0
- **Model Architecture**: `RandomForestClassifier` with StandardScaler & OneHotEncoder Pipeline
- **Target Variable**: `converted` (1 if lead converted to Activated bundle, 0 if Dropped)
- **Framework**: `scikit-learn` 1.6.0

## Intended Use
- Predicts the likelihood that an incoming small/medium business lead converts into an active paid Accel digital connectivity customer.
- Assigns high-propensity leads (deciles 9-10) to top-performing field reps and fast-tracks automated KYC verification.

## Training & Evaluation Data
- **Source**: `data/smb_leads.csv` (5,000 SMB records across 10+ states).
- **Temporal Train Set**: Leads created April 1, 2026  May 31, 2026 (3296 rows, 7.31% positive).
- **Temporal Test Set**: Leads created June 1, 2026  June 30, 2026 (1704 rows, 7.45% positive).
- **Feature Set**:
  - `employee_count`, `num_sites`, `monthly_telecom_spend_inr`
  - `business_type`, `city_tier`, `has_gstin_num`, `current_provider`, `current_internet`, `segment`

## Performance Metrics
- **ROC-AUC**: `0.6684`
- **PR-AUC**: `0.1196`
- **Top-Decile Lift**: `1.883x` (leads in top decile convert at 1.883x baseline rate)

## Fairness & Subgroup Parity
- **Tier 1 City ROC-AUC**: `0.6612`
- **Tier 2 City ROC-AUC**: `0.6614`
- **AUC Parity Ratio**: `0.9997` (demonstrates robust cross-tier generalization)
