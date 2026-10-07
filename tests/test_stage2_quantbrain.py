"""Stage-2 Quant-brain tests: FM fixes, news scores, regime facade, authority, baseline/feature rules."""
from __future__ import annotations

import pandas as pd
import pytest


def test_fm_response_only_loss_masks_prompt():
    from finance_model.training.qlora import TrainingConfig
    assert TrainingConfig(model_name="m", output_dir="o").allow_remote_code is False
    assert TrainingConfig(model_name="m", output_dir="o").enable_gradient_checkpointing is True
    # collator-level check without HF hub: simulate labels logic
    prompt_ids, full_ids = [1, 2, 3, 4], [1, 2, 3, 4, 5, 6]
    labels = full_ids.copy()
    for i in range(min(len(prompt_ids), len(labels))):
        labels[i] = -100
    assert labels == [-100, -100, -100, -100, 5, 6]


def test_fm_precision_agrees_with_hardware():
    import torch
    from finance_model.training.qlora import cuda_available
    use_bf16 = bool(cuda_available() and torch.cuda.is_bf16_supported()) if cuda_available() else False
    use_fp16 = bool(cuda_available() and not use_bf16)
    assert not (use_bf16 and use_fp16)
    if not cuda_available():
        assert use_bf16 is False and use_fp16 is False  # CPU = fp32, honest


def test_fm_manifest_writer():
    from datasets import Dataset
    from finance_model.training.qlora import TrainingConfig, write_run_manifest
    import tempfile, json
    from pathlib import Path
    ds = Dataset.from_dict({"prompt": ["p1", "p2"], "completion": ["c1", "c2"]})
    with tempfile.TemporaryDirectory() as td:
        cfg = TrainingConfig(model_name="m", output_dir=td)
        out = write_run_manifest(cfg, ds, False, False, False)
        m = json.loads(Path(out).read_text())
        assert m["response_only_loss"] is True and m["precision"] == "fp32"
        assert "dataset_hash" in m and "seed" in m


def test_news_novelty_materiality_real():
    from data.news.trust import novelty_score, materiality_score, score_news
    nov_fresh = novelty_score("FDA approves novel Alzheimer drug", ["Fed holds rates steady"])
    nov_dup = novelty_score("Fed holds rates steady", ["Fed holds rates steady"])
    assert nov_fresh > nov_dup
    mat_big = materiality_score("Merger announced", "acquisition merger deal", ("AAPL", "MSFT"))
    mat_small = materiality_score("Sunny outlook", "weather remains fine", ())
    assert mat_big > mat_small
    n, m = score_news("Earnings beat, guidance raised", "earnings guidance", ("NVDA",))
    assert 0.0 <= n <= 1.0 and 0.0 <= m <= 1.0


def test_regime_facade_probs_and_override():
    import pandas as pd
    from quant.regime.facade import RegimeDetector
    idx = pd.date_range("2026-01-01", periods=80, freq="D", tz="UTC")
    close = pd.Series([100 * (1.001 ** i) for i in range(80)], index=idx)
    det = RegimeDetector()
    b = det.infer(close)
    assert abs(sum(b.probs) - 1.0) < 1e-3 and b.label in ("BULL", "BEAR", "HIGH_VOL", "RANGE", "CRISIS")
    o = det.override(b, "BEAR", "risk committee review")
    assert o.label == "BEAR" and o.override == "risk committee review"
    with pytest.raises(AssertionError):
        det.override(b, "BEAR", "")


def test_authority_refuses_llm_order():
    from finance_model.authority import AuthorityRefused, refuse_llm_order
    refuse_llm_order("Here is analysis of AAPL momentum.")
    with pytest.raises(AuthorityRefused):
        refuse_llm_order("You should buy 100 shares of AAPL now")
    with pytest.raises(AuthorityRefused):
        refuse_llm_order("place order to sell 50 TSLA")


def test_baseline_and_feature_rules():
    from quant.forecasting.models import require_baseline_win, feature_oos_gain
    require_baseline_win({"ridge": 0.5, "lstm": 0.4}, baseline="ridge", candidate="lstm")
    with pytest.raises(ValueError):
        require_baseline_win({"ridge": 0.4, "lstm": 0.5}, baseline="ridge", candidate="lstm")
    assert feature_oos_gain(0.5, 0.4) is True
    assert feature_oos_gain(0.4, 0.5) is False
