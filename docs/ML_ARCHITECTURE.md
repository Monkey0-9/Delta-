# ML ARCHITECTURE v1.0 (2026-10-07) — Status: IMPLEMENTED (paper), VALIDATION partial

L1 baselines: Linear/Ridge/Lasso/Logistic/RF/XGB-class. L2: ARIMA/GARCH/Kalman.
L3: MLP/LSTM/GRU/TCN/Temporal-Transformer (CPU, seeded, train-only scaling).
L4: multi-task / cross-asset attention / regime-conditioned / probabilistic.
RULE: every advanced model ships baseline comparison, must win OOS. GPU deferred.
Calibration enforced: uncalibrated models cannot size positions.
Drift: feature+prediction+regime PSI → Models screen + auto-demote.
Registry: TRAINING→CANDIDATE→VALIDATED→SHADOW→APPROVED→ACTIVE→RETIRED.
