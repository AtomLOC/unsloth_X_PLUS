# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

"""Tests for the AMX-aware OpenBLAS thread default.

The default was sized for a laptop: one thread per physical core, capped at 8. That is wrong on an
AMX-class CPU (Sapphire Rapids and newer, or the Cooper Lake / Ice Lake AVX512-BF16 pair), where
wide bf16 matmuls scale with the SMT siblings, so the cap is raised to 32 and the siblings are
kept. The memory-fit clamp is untouched: it is what stops a small machine over-threading.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable

import pytest

import utils.cpu_threads as cpu_threads
from utils.cpu_threads import (
    _AMX_CLASS_DEFAULT_MAX,
    _OPENBLAS_DEFAULT_MAX,
    configure_cpu_threads,
    default_openblas_threads,
)

MB = 1 << 20


def _set_flags(monkeypatch, flags: Iterable[str]) -> None:
    """Pretend the host's CPU advertises these feature words."""
    monkeypatch.setattr(
        cpu_threads.cpu_features, "cpu_flags", lambda *args, **kwargs: frozenset(flags)
    )
    cpu_threads._host_is_amx_class.cache_clear()


@pytest.fixture(autouse = True)
def _plain_host(monkeypatch):
    """Every test states its own CPU class, so none of them depends on the host it runs on."""
    _set_flags(monkeypatch, frozenset())
    # Unbounded memory unless a test says otherwise: the clamp is exercised on its own.
    monkeypatch.setattr(cpu_threads, "_openblas_memory_headroom", lambda: None)
    # Unmeasurable topology unless a test says otherwise: the legacy default is the fallback.
    monkeypatch.setattr(cpu_threads, "measured_physical_cpus", lambda: None)
    yield
    cpu_threads._host_is_amx_class.cache_clear()


# A plain CPU keeps the laptop default exactly as it was: one thread per physical core, capped at 8.
@pytest.mark.parametrize(
    "cpus, expected", [(1, 1), (2, 1), (4, 2), (12, 6), (16, 8), (24, 8), (192, 8)]
)
def test_a_plain_cpu_keeps_the_old_default(cpus, expected, monkeypatch):
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: cpus)

    assert default_openblas_threads() == expected
    assert _OPENBLAS_DEFAULT_MAX == 8


# A measured topology replaces the SMT halving, so a host without SMT stops losing half its cores.
@pytest.mark.parametrize(
    "cpus, physical, expected",
    [
        (1, 1, 1),
        (2, 2, 2),  # 2C/2T: there is no sibling to leave idle
        (4, 2, 2),  # 2C/4T: the measurement agrees with the old halving
        (6, 6, 6),  # this 6C/6T dev host: was 3 threads, measured 1.35-1.6x slower than 6
        (8, 4, 4),  # 4C/8T
        (12, 6, 6),
        (16, 8, 8),
        (32, 32, 8),  # the 8-thread cap still holds on a measured host
        (192, 96, 8),
    ],
)
def test_a_measured_topology_replaces_the_smt_halving(cpus, physical, expected, monkeypatch):
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: cpus)
    monkeypatch.setattr(cpu_threads, "measured_physical_cpus", lambda: physical)

    assert default_openblas_threads() == expected


# An affinity mask wins over the host topology: the process may only run on the narrower set.
def test_an_affinity_mask_narrows_a_measured_host(monkeypatch):
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 4)
    monkeypatch.setattr(cpu_threads, "measured_physical_cpus", lambda: 64)

    assert default_openblas_threads() == 4


# The memory fit still shrinks a measured host: it is about per-thread buffers, not topology.
def test_the_memory_fit_still_shrinks_a_measured_host(monkeypatch):
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 6)
    monkeypatch.setattr(cpu_threads, "measured_physical_cpus", lambda: 6)
    monkeypatch.setattr(cpu_threads, "_openblas_memory_headroom", lambda: 640 * MB)

    assert default_openblas_threads() == 2


# AMX-class hosts keep their own rule; the measurement changes nothing there.
def test_the_measurement_does_not_touch_amx_class_hosts(monkeypatch):
    _set_flags(monkeypatch, {"amx_bf16"})
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 32)
    monkeypatch.setattr(cpu_threads, "measured_physical_cpus", lambda: 16)

    assert default_openblas_threads() == 32


def test_the_measurement_reads_this_host():
    measured = cpu_threads.measured_physical_cpus()

    assert measured is None or (isinstance(measured, int) and measured >= 1)


def test_an_unreadable_psutil_is_not_an_error(monkeypatch):
    class _Broken:
        @staticmethod
        def cpu_count(logical = True):
            if logical:
                return 8
            raise RuntimeError("no topology")

    monkeypatch.setitem(sys.modules, "psutil", _Broken)

    assert cpu_threads.measured_physical_cpus() is None


def test_a_psutil_without_a_physical_count_is_not_an_error(monkeypatch):
    class _Zero:
        @staticmethod
        def cpu_count(logical = True):
            return 8 if logical else 0

    monkeypatch.setitem(sys.modules, "psutil", _Zero)

    assert cpu_threads.measured_physical_cpus() is None


# On an AMX-class CPU the cap is raised and the SMT halving is dropped, so every usable CPU counts.
@pytest.mark.parametrize(
    "cpus, expected", [(1, 1), (2, 2), (8, 8), (16, 16), (32, 32), (64, 32), (192, 32)]
)
def test_an_amx_class_cpu_gets_more_threads(cpus, expected, monkeypatch):
    _set_flags(monkeypatch, {"amx_bf16"})
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: cpus)

    assert default_openblas_threads() == expected
    assert _AMX_CLASS_DEFAULT_MAX == 32


def test_an_amx_class_cpu_beats_the_old_cap(monkeypatch):
    _set_flags(monkeypatch, {"amx_bf16"})
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 64)

    # 32 threads here, where the old rule would have given 8.
    assert default_openblas_threads() == 32
    assert default_openblas_threads() > _OPENBLAS_DEFAULT_MAX


# AMX-BF16 alone is AMX-class; AVX512-BF16 needs the AVX512 foundation set beside it.
def test_the_amx_class_rule_reads_the_cpu_flags():
    assert cpu_threads._is_amx_class(frozenset({"amx_bf16"})) is True
    assert cpu_threads._is_amx_class(frozenset({"avx512_bf16", "avx512f"})) is True
    assert cpu_threads._is_amx_class(frozenset({"avx512_bf16"})) is False
    assert cpu_threads._is_amx_class(frozenset({"avx2", "fma"})) is False
    # An unmeasurable CPU (empty flags) is not AMX-class: it keeps the ordinary default.
    assert cpu_threads._is_amx_class(frozenset()) is False
    assert cpu_threads._is_amx_class(None) is False
    # A raw flag line is read as words, not as one flag.
    assert cpu_threads._is_amx_class("amx_bf16 avx512f") is True


def test_the_avx512_bf16_pair_counts_as_amx_class(monkeypatch):
    _set_flags(monkeypatch, {"avx512_bf16", "avx512f"})
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 64)

    assert cpu_threads._host_is_amx_class() is True
    assert default_openblas_threads() == 32


def test_avx512_bf16_without_avx512f_is_not_amx_class(monkeypatch):
    _set_flags(monkeypatch, {"avx512_bf16"})
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 64)

    assert cpu_threads._host_is_amx_class() is False
    assert default_openblas_threads() == 8


# Windows and macOS have no /proc/cpuinfo, so the flags are empty and nothing changes there.
def test_empty_cpu_flags_leave_the_default_unchanged(monkeypatch):
    _set_flags(monkeypatch, frozenset())
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 64)

    assert cpu_threads._host_is_amx_class() is False
    assert default_openblas_threads() == 8


# An unreadable CPU must not crash the thread default either.
def test_an_unreadable_cpu_falls_back_to_the_plain_default(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("no /proc/cpuinfo")

    monkeypatch.setattr(cpu_threads.cpu_features, "cpu_flags", boom)
    cpu_threads._host_is_amx_class.cache_clear()
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 64)

    assert cpu_threads._host_is_amx_class() is False
    assert default_openblas_threads() == 8


# The memory clamp is what stops a small machine over-threading, and it still wins on AMX.
def test_the_memory_clamp_still_wins_on_an_amx_class_host(monkeypatch):
    _set_flags(monkeypatch, {"amx_bf16"})
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 64)
    monkeypatch.setattr(cpu_threads, "_openblas_memory_headroom", lambda: 1280 * MB)

    # 1280 MB of headroom at 32 MB per worker and a 10% share fits 4 threads, not 32.
    assert default_openblas_threads() == 4


@pytest.mark.parametrize("headroom_mb", [None, 0, 100, 320, 640, 1280, 2600])
def test_the_thread_count_is_never_zero_or_negative(headroom_mb, monkeypatch):
    _set_flags(monkeypatch, {"amx_bf16"})
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 64)
    monkeypatch.setattr(
        cpu_threads,
        "_openblas_memory_headroom",
        lambda: None if headroom_mb is None else headroom_mb * MB,
    )

    threads = default_openblas_threads()

    assert threads >= 1


# The configured environment picks up the AMX default too.
def test_the_seeded_openblas_value_follows_the_cpu_class(monkeypatch):
    _set_flags(monkeypatch, {"amx_bf16"})
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 64)
    env = {}

    configure_cpu_threads(env)

    assert env["OPENBLAS_NUM_THREADS"] == "32"


def test_a_plain_cpu_still_seeds_the_old_value(monkeypatch):
    monkeypatch.setattr(cpu_threads, "_usable_cpus", lambda: 64)
    env = {}

    configure_cpu_threads(env)

    assert env["OPENBLAS_NUM_THREADS"] == "8"
