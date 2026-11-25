# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

"""The memoised PATH lookup behind llama-server discovery.

`/api/inference/status` resolves a llama-server binary up to twice per poll and the UI polls it
about 1.7 times a second on the Hub. The old code called `shutil.which("llama-server")` on every
one of those resolutions, which walks the entire PATH (473 `stat` calls on the dev host, ~14 ms):
28.6 ms of a 39.1 ms response, measured by cProfile over 25 requests.

The memo must not hide an install, so these tests pin both halves: repeated lookups inside the
window hit once, a miss is memoised too (a miss is the common case and the expensive one), and
the window expiring re-runs the lookup. Settings-dependent discovery steps are not memoised and
are covered by their own tests.
"""

from __future__ import annotations

import pytest

from core.inference import llama_cpp


@pytest.fixture(autouse = True)
def clean_cache(monkeypatch):
    with llama_cpp._path_binary_lock:
        llama_cpp._path_binary_cache.clear()
    yield
    with llama_cpp._path_binary_lock:
        llama_cpp._path_binary_cache.clear()


@pytest.fixture
def which_calls(monkeypatch):
    """Record every real PATH walk instead of performing one."""
    calls: list[str] = []

    def fake_which(name: str):
        calls.append(name)
        return f"/fake/bin/{name}"

    monkeypatch.setattr(llama_cpp.shutil, "which", fake_which)
    return calls


def test_repeated_lookups_walk_the_path_once(which_calls):
    first = llama_cpp._path_binary("llama-server")
    second = llama_cpp._path_binary("llama-server")
    third = llama_cpp._path_binary("llama-server")

    assert first == second == third == "/fake/bin/llama-server"
    assert which_calls == ["llama-server"], f"the PATH walk must happen once, saw {len(which_calls)}"


def test_a_miss_is_memoised(which_calls, monkeypatch):
    """Absence is the common case on a machine with no system llama.cpp, and the full walk is the cost."""
    monkeypatch.setattr(llama_cpp.shutil, "which", lambda name: which_calls.append(name))
    assert llama_cpp._path_binary("llama-server") is None
    assert llama_cpp._path_binary("llama-server") is None
    assert len(which_calls) == 1


def test_the_window_expiring_re_runs_the_lookup(which_calls, monkeypatch):
    """A binary installed while the app is running is still found, within one window."""
    assert llama_cpp._path_binary("llama-server") == "/fake/bin/llama-server"
    monkeypatch.setattr(llama_cpp, "_PATH_BINARY_TTL_SECONDS", 0.0)
    assert llama_cpp._path_binary("llama-server") == "/fake/bin/llama-server"
    assert len(which_calls) == 2


def test_each_binary_name_is_cached_separately(which_calls):
    llama_cpp._path_binary("llama-server")
    llama_cpp._path_binary("llama-quantize")
    llama_cpp._path_binary("llama-server")

    assert sorted(which_calls) == ["llama-quantize", "llama-server"]


def test_discovery_uses_the_memo(which_calls, monkeypatch):
    """The call site itself must go through the memo, not just the helper."""
    import inspect

    source = inspect.getsource(llama_cpp.LlamaCppBackend._find_llama_server_binary)
    assert "shutil.which(" not in source, "discovery went back to an uncached PATH walk"
    assert "_path_binary(" in source
