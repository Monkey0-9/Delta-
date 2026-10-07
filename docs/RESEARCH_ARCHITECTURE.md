# RESEARCH ARCHITECTURE v1.0 (2026-10-07) — Status: PARTIAL

Loop: HYPOTHESIS → DATASET → PIT-CHECK → FEATURE → BASELINE → MODEL →
WALK-FORWARD → COSTS → STATISTICS → STRESS → REPORT (budgets enforced).
Agents: ResearchPlanner/Hypothesis/Dataset/Experiment/Backtest/Validator/Failure/Report.
Memory stores Experiment/Hypothesis/Dataset/Features/Model/Result/Failure/Reason/Decision.
Repeat-failed-idea warns with prior EXP-ID. Budgets: max experiments, compute, time.
Human gates: promote/demote/retire need approval + reason.
