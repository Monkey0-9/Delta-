# MODEL LIFECYCLE v1.0 (2026-10-07)

TRAINING → CANDIDATE → VALIDATED → SHADOW → APPROVED → ACTIVE → RETIRED.
Each transition: dataset_hash + feature_version + code_sha + params + train/val/OOS
periods + metrics + failure cases + calibration + approval + reason. No-skip enforced.
reproduce(EXP-ID) verifies manifest hash. Decay auto-demotes; capacity breach retires.
Drift (PSI) → Models screen + auto-demote. Uncalibrated → cannot size.
