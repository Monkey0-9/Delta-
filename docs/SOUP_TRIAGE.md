# Soup triage — DELTA decision record (2026-09-30)

Upstream: https://github.com/MakazhanAlpamys/Soup (Apache-2.0, LLM fine-tuning/post-training CLI).
DELTA: proprietary. No source copied. License rule: any future vendored
Apache-2.0 file must retain its header + NOTICE attribution.

| # | Soup capability | Delta requirement | Current Delta | Gap | Decision |
|---|---|---|---|---|---|
| 1 | `config/schema.py` single source of truth; unknown keys REJECTED (v0.75) | Fail-closed config; typos must not silently change risk | Config exists but unknown-key behavior untested | Strict schema gate missing | **ADAPT**: implement strict unknown-key rejection for risk/execution configs (pattern only, no code copied) |
| 2 | Dataset scorecards / quality tooling | Data-quality gates before PIT/backtest | PIT pipeline correct; quality gates ad-hoc | Standardized gate | **ADAPT**: mirror scorecard *concept* in `data/market/quality.py` |
| 3 | Experiment tracking / repro receipts / BOM | Experiment provenance (§4/§22) | Partial registries | Unified experiment ID | **REFERENCE ONLY** |
| 4 | Training orchestration (SFT/DPO/LoRA, layer streaming) | Finance ML lifecycle | `quant/forecasting`, model zoo exist | No LLM post-training need | **REJECT** for training loop; **WRAP** only if a finance LLM adapter is ever needed (isolated process, no risk-path access) |
| 5 | Hardware-fit / VRAM guide, `doctor` | Perf boundaries (§35/36) | Benchmarks exist | None blocking | **REFERENCE ONLY** |
| 6 | TUI/dashboard patterns | Trader TUI (§28) | Custom TUI in flight | Different UX constraints | **REFERENCE ONLY** |
| 7 | Supply-chain controls (scan/sign/BOM) | Security (§33) | Vault AES-256-GCM solid | SBOM/signing | **ADAPT** process, not code |

No transitive dependencies introduced. No NOTICE obligations triggered (no redistribution of Soup code).
