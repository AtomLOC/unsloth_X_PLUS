# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

"""A fork build must never be told that PyPI has an upgrade.

PyPI's ``unsloth`` is upstream's package. The fork's wheels carry a local segment
(``2026.11.7+xplus.1``), which is greater than the same base version upstream publishes, so before
this guard the check could offer "update available" for the next upstream release and the button would
``pip install unsloth`` over the fork, deleting the X+ engines on a running install.
"""

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from utils import update_status  # noqa: E402


def _pypi(latest: str) -> update_status.LatestVersionResult:
    return update_status.LatestVersionResult(latest_version = latest, checked_at = "2026-11-20T00:00:00Z")


@pytest.fixture
def pypi_install(monkeypatch):
    """Pretend the suite is a real PyPI install so the comparison path is reachable at all."""
    monkeypatch.setattr(update_status, "detect_install_source", lambda: "pypi")
    monkeypatch.delenv(update_status.DISABLE_ENV_VAR, raising = False)
    monkeypatch.delenv(update_status.FAKE_UPDATE_ENV_VAR, raising = False)

    def _set(latest: str):
        monkeypatch.setattr(update_status, "get_latest_pypi_version", lambda: _pypi(latest))

    return _set


def test_a_fork_build_is_not_upgraded_from_pypi(pypi_install):
    # PyPI is two releases ahead; that is still not this install's upgrade.
    pypi_install("2026.12.0")
    status = update_status.get_studio_update_status("2026.11.7+xplus.1")

    assert status["update_available"] is False
    assert status["can_show_web_notification"] is False
    assert status["latest_version"] is None
    assert status["reason"] == "fork_build"


def test_the_fork_verdict_does_not_depend_on_the_pypi_answer(pypi_install):
    # Same version as the base upstream release, which the old comparison called "not older".
    pypi_install("2026.11.7")
    assert update_status.get_studio_update_status("2026.11.7+xplus.9")["reason"] == "fork_build"


def test_an_upstream_build_still_compares_with_pypi(pypi_install):
    # The guard must not disarm upstream's own update banner.
    pypi_install("2026.12.0")
    status = update_status.get_studio_update_status("2026.11.7")

    assert status["update_available"] is True
    assert status["latest_version"] == "2026.12.0"


def test_upstream_is_not_offered_its_own_current_version(pypi_install):
    pypi_install("2026.11.7")
    assert update_status.get_studio_update_status("2026.11.7")["reason"] == "current_not_older"


@pytest.mark.parametrize(
    "version, expected",
    [
        ("2026.11.7+xplus.1", True),
        ("2026.11.7+xplus", True),
        ("2026.11.7+XPLUS.1", True),
        ("2026.11.7+cu13", False),
        ("2026.11.7", False),
        ("dev", False),
        ("not a version", False),
    ],
)
def test_fork_detection_is_the_local_segment(version, expected):
    assert update_status.is_fork_build(version) is expected


def test_a_local_checkout_stays_local(pypi_install, monkeypatch):
    # A checkout is not on PyPI at all, so it keeps its own reason and never reaches the fork branch.
    monkeypatch.setattr(update_status, "detect_install_source", lambda: "editable")
    pypi_install("2026.12.0")
    assert update_status.get_studio_update_status("2026.11.7+xplus.1")["reason"] == "local_source"
