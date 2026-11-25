# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

"""Tests for the CPU training tuning plan.

The planner is a pure function of its measurements and this host has no torch, so every rule is
exercised directly: the SMT thread approximation and its clamps, the memory-driven thread
halving, the platform dataloader-worker policy, the checkpointing and dtype thresholds, the
frozen shape of the plan, and the sentence quality of the recorded reasons.
"""

from __future__ import annotations

import sys
import types
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.training.cpu_tuning import cpu_base_load_kwargs, measured_physical_cpus, plan_cpu_training
from utils.cpu_features import bf16_summary, cpu_flags, supports_fast_bf16

GB = 1024**3

# A trimmed /proc/cpuinfo in the shape the kernels actually emit: x86 spells the feature line
# "flags", arm64 spells it "Features", and both repeat it once per processor.
X86_CPUINFO = """processor\t: 0
vendor_id\t: GenuineIntel
model name\t: Intel(R) Xeon(R) Gold 6430
flags\t\t: fpu vme de pse msr avx2 avx512f avx512_bf16 amx_tile amx_bf16

processor\t: 1
vendor_id\t: GenuineIntel
flags\t\t: fpu vme de pse msr avx2 avx512f avx512_bf16 amx_tile amx_bf16
"""

ARM64_CPUINFO = """processor\t: 0
BogoMIPS\t: 48.00
Features\t: fp asimd evtstrm aes pmull sha1 sha2 crc32 atomics asimdhp\n"""


def plan(**measurements):
    """Plan with the measurements the test does not care about marked unknown."""
    unknown = {
        "usable_cpus": None,
        "available_memory_bytes": None,
        "fp32_weight_bytes": None,
    }
    unknown.update(measurements)
    return plan_cpu_training(**unknown)


def test_threads_are_one_per_approximate_physical_core():
    # SMT siblings add little to a GEMM, so the usable CPU count is halved past two CPUs.
    assert plan(usable_cpus = 16).torch_threads == 8
    assert plan(usable_cpus = 8).torch_threads == 4
    assert plan(usable_cpus = 3).torch_threads == 1


def test_thread_count_is_clamped_to_at_least_one_and_never_more_than_the_cpus():
    # A 2-CPU box is taken at face value; halving it would leave the GEMM single-threaded.
    assert plan(usable_cpus = 1).torch_threads == 1
    assert plan(usable_cpus = 2).torch_threads == 2
    assert plan(usable_cpus = 17).torch_threads == 8
    assert plan(usable_cpus = -4).torch_threads == 1


def test_a_measured_physical_count_replaces_the_halving_estimate():
    # A 6C/6T host: the halving heuristic would train on three cores, the measurement keeps six.
    assert plan(usable_cpus = 6, physical_cpus = 6).torch_threads == 6
    # 16 logical / 8 physical agrees with the old estimate, so SMT hosts are unchanged.
    assert plan(usable_cpus = 16, physical_cpus = 8).torch_threads == 8
    # An affinity mask narrows what this process may use, and the mask wins over the package.
    assert plan(usable_cpus = 4, physical_cpus = 12).torch_threads == 2
    # Nonsense measurements are ignored rather than trusted.
    assert plan(usable_cpus = 8, physical_cpus = 0).torch_threads == 4
    assert plan(usable_cpus = 8, physical_cpus = -2).torch_threads == 4


def test_an_unmeasured_physical_count_keeps_the_smt_estimate():
    estimate = plan(usable_cpus = 6)
    assert estimate.torch_threads == 3
    assert any("could not be measured" in reason for reason in estimate.reasons)


def test_amx_class_hosts_keep_the_usable_count_capped_at_32():
    # AMX bf16 matmuls scale with SMT siblings, so halving them is the wrong trade there too.
    assert plan(usable_cpus = 16, fast_bf16 = True).torch_threads == 16
    assert plan(usable_cpus = 64, fast_bf16 = True).torch_threads == 32


def test_the_loader_measures_the_physical_count_and_passes_it_in():
    # Source-level because trainer imports torch at module scope and this host has none; a rule
    # this easy to drop back to the heuristic must be pinned where it is wired.
    trainer = (Path(__file__).resolve().parents[1] / "core" / "training" / "trainer.py")
    source = trainer.read_text(encoding = "utf-8")
    assert "physical_cpus = measured_physical_cpus()" in source


def test_measured_physical_cpus_answers_a_positive_count_or_nothing():
    measured = measured_physical_cpus()
    assert measured is None or measured >= 1


def _stub_transformers(monkeypatch, version: str) -> None:
    stub = types.ModuleType("transformers")
    stub.__version__ = version
    monkeypatch.setitem(sys.modules, "transformers", stub)


@pytest.fixture
def _dtype_cache():
    from utils.transformers_dtype import _has_torch_dtype_kwarg

    _has_torch_dtype_kwarg.cache_clear()
    yield
    _has_torch_dtype_kwarg.cache_clear()


# transformers renamed the load dtype in 4.56; the floor here is 4.52, where the new name is
# dropped instead of raising, so a bf16 choice would silently load the checkpoint's own width.
def test_cpu_base_load_kwargs_speaks_the_installed_transformers_dialect(monkeypatch, _dtype_cache):
    _stub_transformers(monkeypatch, "4.52.4")
    old = cpu_base_load_kwargs("bfloat16", token = "tok", revision = "rev")
    assert old["torch_dtype"] == "bfloat16" and "dtype" not in old

    _stub_transformers(monkeypatch, "5.1.0")
    # The version is read once per process in production; the test changes it mid-run.
    from utils.transformers_dtype import _has_torch_dtype_kwarg

    _has_torch_dtype_kwarg.cache_clear()
    new = cpu_base_load_kwargs("bfloat16", token = "tok", revision = "rev")
    assert new["dtype"] == "bfloat16" and "torch_dtype" not in new

    # Both dialects carry the rest of the CPU load: streamed shards and the HF plumbing.
    for kwargs in (old, new):
        assert kwargs["low_cpu_mem_usage"] is True
        assert kwargs["token"] == "tok"
        assert kwargs["revision"] == "rev"
        assert kwargs["trust_remote_code"] is False
        assert kwargs["local_files_only"] is False


# The loader and the exporter must share the rule: the old TypeError retry never fired, because
# the wrong name is accepted and ignored.
def test_the_cpu_loader_and_the_exporter_share_the_dtype_rule():
    backend = Path(__file__).resolve().parents[1]
    trainer = (backend / "core" / "training" / "trainer.py").read_text(encoding = "utf-8")
    export = (backend / "core" / "export" / "cpu_export.py").read_text(encoding = "utf-8")

    assert "load_kwargs = cpu_base_load_kwargs(" in trainer
    assert '"dtype": dtype,' not in trainer
    assert "**dtype_kwargs(dtype)" in export
    assert "torch_dtype=dtype" not in export

def test_memory_pressure_halves_the_thread_count_and_adds_a_reason():
    # 7 GB of fp32 weights in 10 GB of RAM is over 60%: per-thread buffers decide the run's fate.
    tuned = plan(
        usable_cpus = 16,
        available_memory_bytes = 10 * GB,
        fp32_weight_bytes = 7 * GB,
    )
    assert tuned.torch_threads == 4
    assert any("60%" in reason for reason in tuned.reasons)
    # Exactly 60% does not clamp.
    at_boundary = plan(
        usable_cpus = 16,
        available_memory_bytes = 10 * GB,
        fp32_weight_bytes = 6 * GB,
    )
    assert at_boundary.torch_threads == 8


def test_the_memory_clamp_never_drops_the_run_below_one_thread():
    # 3 usable CPUs halve to 1 thread, which the clamp must then halve to 1, not 0.
    tuned = plan(
        usable_cpus = 3,
        available_memory_bytes = 10 * GB,
        fp32_weight_bytes = 7 * GB,
    )
    assert tuned.torch_threads == 1


def test_unknown_inputs_yield_the_conservative_plan():
    conservative = plan_cpu_training(
        usable_cpus = None,
        available_memory_bytes = None,
        fp32_weight_bytes = None,
        platform = None,
        supports_sdpa = None,
    )
    assert conservative.torch_threads == 1
    assert conservative.interop_threads == 1
    assert conservative.attn_implementation == "eager"
    assert conservative.dataloader_workers == 0
    assert conservative.gradient_checkpointing is False
    assert conservative.dtype == "float32"


def test_interop_threads_stay_at_one_on_every_machine():
    assert plan(usable_cpus = 16).interop_threads == 1
    assert plan().interop_threads == 1


def test_attention_falls_back_to_eager_without_sdpa_support():
    assert plan(supports_sdpa = True).attn_implementation == "sdpa"
    assert plan(supports_sdpa = False).attn_implementation == "eager"


def test_dataloader_workers_are_zero_on_the_spawn_platforms():
    # Spawned workers would re-import the training module; the hazard is not worth it here.
    assert plan(usable_cpus = 16, platform = "win32").dataloader_workers == 0
    assert plan(usable_cpus = 16, platform = "darwin").dataloader_workers == 0


def test_dataloader_workers_scale_on_linux_but_stay_capped_and_floored():
    assert plan(usable_cpus = 32, platform = "linux").dataloader_workers == 4
    assert plan(usable_cpus = 16, platform = "linux").dataloader_workers == 4
    assert plan(usable_cpus = 8, platform = "linux").dataloader_workers == 2
    assert plan(usable_cpus = 4, platform = "linux").dataloader_workers == 1
    # An unknown CPU count keeps the conservative zero even on Linux.
    assert plan(usable_cpus = None, platform = "linux").dataloader_workers == 0


def test_gradient_checkpointing_flips_just_above_forty_percent():
    # Over 40% of the RAM in fp32 weights the activations are recomputed instead of kept.
    at_boundary = plan(available_memory_bytes = 10 * GB, fp32_weight_bytes = 4 * GB)
    over_boundary = plan(
        available_memory_bytes = 10 * GB,
        fp32_weight_bytes = 4 * GB + 1,
    )
    assert at_boundary.gradient_checkpointing is False
    assert over_boundary.gradient_checkpointing is True
    # Unknown memory keeps checkpointing off.
    assert plan(fp32_weight_bytes = 7 * GB).gradient_checkpointing is False


def test_dtype_flips_to_bfloat16_only_when_fp32_cannot_fit():
    # The fit rule is cpu_fp32_weights_fit: the fp32 weights plus a 2 GiB activation headroom
    # inside the available RAM, the same rule the loader applied before this module existed.
    fits = plan(available_memory_bytes = 10 * GB, fp32_weight_bytes = 8 * GB - 1)
    does_not_fit = plan(available_memory_bytes = 10 * GB, fp32_weight_bytes = 8 * GB + 1)
    assert fits.dtype == "float32"
    assert does_not_fit.dtype == "bfloat16"
    assert plan(available_memory_bytes = 4 * GB, fp32_weight_bytes = 6 * GB).dtype == "bfloat16"
    # Unknown measurements keep fp32.
    assert plan().dtype == "float32"


def test_the_plan_is_frozen():
    tuned = plan(usable_cpus = 8)
    with pytest.raises(FrozenInstanceError):
        tuned.torch_threads = 2  # type: ignore[misc]


def test_every_reason_is_a_plain_sentence():
    rich = plan_cpu_training(
        usable_cpus = 16,
        available_memory_bytes = 10 * GB,
        fp32_weight_bytes = 7 * GB,
        platform = "win32",
        supports_sdpa = False,
    )
    conservative = plan_cpu_training(
        usable_cpus = None,
        available_memory_bytes = None,
        fp32_weight_bytes = None,
        platform = None,
        supports_sdpa = None,
    )
    assert rich.reasons
    for tuned in (rich, conservative):
        for reason in tuned.reasons:
            assert " " in reason
            assert "_" not in reason


def test_cpu_flags_read_the_x86_flags_line_and_lowercase_it():
    flags = cpu_flags(platform = "linux", cpuinfo_text = X86_CPUINFO)
    assert "amx_bf16" in flags
    assert "avx512_bf16" in flags
    assert "avx2" in flags
    # The union over both processors is the host's set, and only the flag words are kept.
    assert "vendor_id" not in flags
    assert all(flag == flag.lower() for flag in flags)


def test_cpu_flags_read_the_arm64_features_line():
    flags = cpu_flags(platform = "linux", cpuinfo_text = ARM64_CPUINFO)
    assert "asimd" in flags
    assert "aes" in flags
    assert "bogomips" not in flags
    assert "amx_bf16" not in flags


def test_cpu_flags_without_injected_text_are_empty_on_windows_and_macos():
    # Unmeasurable, not "no features": neither platform has a cpuinfo file worth reading.
    assert cpu_flags(platform = "win32") == frozenset()
    assert cpu_flags(platform = "darwin") == frozenset()
    assert cpu_flags(platform = "linux", cpuinfo_text = "") == frozenset()


def test_supports_fast_bf16_covers_each_hardware_generation():
    # AMX-BF16: Sapphire Rapids and newer. AVX512-BF16 plus AVX512F: Cooper Lake / Ice Lake.
    assert supports_fast_bf16(frozenset({"amx_bf16"})) is True
    assert supports_fast_bf16(frozenset({"avx512_bf16", "avx512f"})) is True
    # AVX512-BF16 alone cannot execute without the AVX512 foundation set.
    assert supports_fast_bf16(frozenset({"avx512_bf16"})) is False
    # AVX2 alone is every mainstream x86 CPU since Haswell: bf16 here is emulated.
    assert supports_fast_bf16(frozenset({"avx2", "fma"})) is False
    # Apple Silicon (M1 and newer) runs bf16 natively; Intel Macs do not.
    assert supports_fast_bf16(frozenset(), platform = "darwin", machine = "arm64") is True
    assert supports_fast_bf16(frozenset(), platform = "darwin", machine = "x86_64") is False
    # Empty means unmeasurable, and the safe answer there is fp32.
    assert supports_fast_bf16(frozenset()) is False


def test_supports_fast_bf16_reads_the_injected_cpuinfo():
    assert supports_fast_bf16(cpu_flags(platform = "linux", cpuinfo_text = X86_CPUINFO)) is True
    assert supports_fast_bf16(cpu_flags(platform = "linux", cpuinfo_text = ARM64_CPUINFO)) is False


def test_bf16_summary_is_a_prose_sentence_for_every_case():
    cases = (
        bf16_summary(frozenset({"amx_bf16"}), platform = "linux", machine = "x86_64"),
        bf16_summary(
            frozenset({"avx512_bf16", "avx512f"}), platform = "linux", machine = "x86_64"
        ),
        bf16_summary(frozenset({"avx512_bf16"}), platform = "linux", machine = "x86_64"),
        bf16_summary(frozenset(), platform = "darwin", machine = "arm64"),
        bf16_summary(frozenset(), platform = "win32", machine = "AMD64"),
        bf16_summary(frozenset({"avx2", "fma"}), platform = "linux", machine = "x86_64"),
    )
    for sentence in cases:
        assert " " in sentence
        assert "_" not in sentence
    assert cases[0].startswith("This CPU has AMX-BF16")
    assert "AVX512-BF16" in cases[1]
    assert "AVX512F" in cases[2]
    assert "Apple Silicon" in cases[3]
    # The empty set is unmeasurable, so its sentence must not claim the CPU lacks bf16.
    assert "could not be measured" in cases[4]
    assert "no bf16" in cases[5]


def test_bf16_summary_never_raises_on_a_malformed_flag_argument():
    assert bf16_summary(None)
    assert bf16_summary(42)  # not iterable: still a sentence, not an exception


def test_plan_uses_bfloat16_when_the_cpu_has_fast_bf16():
    tuned = plan(available_memory_bytes = 10 * GB, fp32_weight_bytes = 4 * GB, fast_bf16 = True)
    assert tuned.dtype == "bfloat16"
    assert any("hardware" in reason for reason in tuned.reasons)
    # The reason names the hardware, not the memory, because the weights did fit.
    assert not any("cannot fit" in reason for reason in tuned.reasons)


def test_the_memory_reason_wins_over_the_hardware_reason_when_fp32_does_not_fit():
    tuned = plan(
        available_memory_bytes = 10 * GB,
        fp32_weight_bytes = 9 * GB,
        fast_bf16 = True,
    )
    assert tuned.dtype == "bfloat16"
    assert any("cannot fit" in reason for reason in tuned.reasons)
    assert not any("hardware" in reason for reason in tuned.reasons)


def test_fast_bf16_defaults_to_false_and_leaves_the_existing_dtype_rule_unchanged():
    fits = plan(available_memory_bytes = 10 * GB, fp32_weight_bytes = 8 * GB - 1)
    does_not_fit = plan(available_memory_bytes = 10 * GB, fp32_weight_bytes = 8 * GB + 1)
    assert fits.dtype == "float32"
    assert does_not_fit.dtype == "bfloat16"
    assert plan().dtype == "float32"
    assert plan(fast_bf16 = False).dtype == "float32"
