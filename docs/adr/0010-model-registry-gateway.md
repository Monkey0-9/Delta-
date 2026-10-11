# ADR 0010 — One model registry + gateway + probe set (audit §5/P1)

- Version: 1.0 / Date: 2026-10-11 / Status: accepted
- Context: three overlapping surfaces — `ai/registry.py` + `ai/gateway.py`
  (role isolation, verification principles), `models/router.py` +
  `models/registry.py` (hot-swap, role routing, silent fallback), and
  `delta_os/model_catalogue.py` + `delta_os/llm_gateway.py` (UI truth,
  provider rails). An explicit request for an unknown model silently
  invoked a different model (fixed: visible ValueError).
- Decision:
  1. Canonical: `ai/registry.py` + `ai/gateway.py` (principles) fronted by
     `delta_os/model_catalogue.py` (UI truth with the §4 status ladder:
     READY only after live probe; CONFIGURED/INVALID otherwise) and
     `delta_os/llm_gateway.py` (provider rails with verified IDs).
  2. `models/router.py` keeps hot-swap mechanics but routes through the
     catalogue ladder (no silent substitution — enforced by test).
  3. `models/registry.py` effort heuristics stay labeled conveniences;
     capability proof comes from probes + benchmarks, never stage labels.
  4. Retired provider IDs are removed at the source (deepseek-reasoner ->
     deepseek-v4-pro; claude-5-5 deleted); unverifiable IDs stay
     UNVERIFIED and unroutable.
  5. Gemini authenticates via header, never query string; keys never land
     in logs (scrub-tested).
- Consequences: `tests/test_p1_retired_paths.py` bars retired imports from
  production paths; any new provider ID needs docs + probe evidence.
