# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

import json
from pathlib import Path

import pytest

from core.training import fit


def _model(tmp_path: Path) -> Path:
    directory = tmp_path / "model"
    directory.mkdir()
    (directory / "config.json").write_text(
        json.dumps(
            {
                "model_type": "llama",
                "hidden_size": 512,
                "intermediate_size": 2048,
                "num_hidden_layers": 8,
                "num_attention_heads": 8,
                "num_key_value_heads": 8,
                "vocab_size": 32000,
            }
        ),
        encoding = "utf-8",
    )
    return directory


def test_lora_fit_reports_a_breakdown_and_headroom(tmp_path):
    report = fit.estimate(
        {
            "model": str(_model(tmp_path)),
            "method": "lora",
            "batch_size": 1,
            "max_seq_length": 1024,
            "gradient_accumulation": 8,
            "lora_rank": 16,
            "gpu_memory_gb": 24,
        }
    )
    assert report["verdict"] == "fits"
    assert report["params"] > 0
    assert report["breakdown"]["total_gb"] > 0
    assert report["headroom_gb"] > 0
    assert report["suggestions"] == []


def test_full_training_is_heavier_than_qlora_and_gets_levers(tmp_path):
    model = str(_model(tmp_path))
    common = {
        "model": model,
        "batch_size": 4,
        "max_seq_length": 8192,
        "lora_rank": 64,
        "gpu_memory_gb": 4,
    }
    qlora = fit.estimate({**common, "method": "qlora"})
    full = fit.estimate({**common, "method": "full"})
    assert full["required_gb"] > qlora["required_gb"]
    assert full["verdict"] == "over"
    assert any("batch size" in item for item in full["suggestions"])
    assert any("sequence length" in item for item in full["suggestions"])
    assert any("batch size" in item for item in qlora["suggestions"])


def test_no_gpu_size_is_reported_as_unknown_not_as_fits(tmp_path):
    report = fit.estimate({"model": str(_model(tmp_path)), "method": "lora"})
    assert report["budget_gb"] is None
    assert report["verdict"] == "unknown"
    assert any("did not report" in item for item in report["suggestions"])


def test_fit_rejects_a_model_without_a_parameter_count(tmp_path):
    directory = tmp_path / "broken"
    directory.mkdir()
    (directory / "config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        fit.estimate({"model": str(directory), "method": "lora"})
    with pytest.raises(ValueError):
        fit.estimate({"model": "", "method": "lora"})

def test_a_named_target_outranks_the_memory_figure_the_page_sent(tmp_path, monkeypatch):
    """The wizard always sends gpu_memory_gb when a GPU is reported, so a target-sized budget that
    only ran without it would never run at all on the hosts it exists for."""
    monkeypatch.setattr(
        fit,
        "_target_budget_gb",
        lambda _spec: (10.0, "target:igpu", ["This GPU shares system memory."], "igpu"),
    )

    report = fit.estimate(
        {
            "model": str(_model(tmp_path)),
            "method": "lora",
            "compute_target": "igpu",
            "gpu_memory_gb": 0.5,
        }
    )

    assert report["budget_gb"] == 10.0
    assert report["budget_source"] == "target:igpu"
    assert report["target_notes"] == ["This GPU shares system memory."]


def test_an_integrated_target_is_sized_in_sixteen_bit_and_never_offered_four_bit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fit,
        "_target_budget_gb",
        lambda _spec: (0.1, "target:igpu", ["This GPU shares system memory."], "igpu"),
    )

    report = fit.estimate(
        {
            "model": str(_model(tmp_path)),
            "method": "lora",
            "compute_target": "igpu",
            "load_in_4bit": True,
            "batch_size": 4,
            "max_seq_length": 8192,
        }
    )

    # The launch path clears 4-bit on this device (bitsandbytes has no integrated kernels), so an
    # estimate that kept it would size the weights 3.6x too small and then suggest the refusal.
    assert report["config"]["load_in_4bit"] is False
    assert report["verdict"] == "over"
    assert not any("4-bit" in suggestion for suggestion in report["suggestions"])


def test_a_discrete_target_still_sizes_the_requested_four_bit_load(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fit,
        "_target_budget_gb",
        lambda _spec: (24.0, "target:dgpu", [], "dgpu"),
    )

    report = fit.estimate(
        {
            "model": str(_model(tmp_path)),
            "method": "lora",
            "compute_target": "dgpu",
            "load_in_4bit": True,
            "batch_size": 1,
            "max_seq_length": 1024,
        }
    )

    assert report["config"]["load_in_4bit"] is True
    assert report["verdict"] == "fits"

def test_a_malformed_memory_figure_is_rejected_even_when_the_target_resolves(tmp_path, monkeypatch):
    # The target's own budget used to replace the value before it was parsed, so a typo only
    # surfaced on hosts where no target resolved.
    monkeypatch.setattr(fit, "_target_budget_gb", lambda _spec: (10.0, "target:cpu", [], "cpu"))

    with pytest.raises(ValueError):
        fit.estimate(
            {
                "model": str(_model(tmp_path)),
                "method": "lora",
                "compute_target": "cpu",
                "gpu_memory_gb": "lots",
            }
        )

def test_an_unsizable_target_falls_back_to_the_figure_the_page_sent(tmp_path, monkeypatch):
    monkeypatch.setattr(fit, "_target_budget_gb", lambda _spec: (None, "unresolved", ["no probe"], None))

    report = fit.estimate(
        {
            "model": str(_model(tmp_path)),
            "method": "lora",
            "compute_target": "npu",
            "gpu_memory_gb": 24,
        }
    )

    # A budget the caller stated is still better than none; the target's note explains the gap.
    assert report["budget_gb"] == 24.0
    assert report["budget_source"] == "explicit"
