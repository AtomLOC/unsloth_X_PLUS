# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

"""The desktop secret's validated-once memo.

The shipped desktop shell sends ``X-Desktop-Secret`` on every ``/api/health`` poll, and validating it
spends 100 000 PBKDF2 rounds (~14 ms measured on the dev host). The secret is 48 bytes of
``secrets.token_urlsafe``, so the KDF protects a dumped ``app_secrets`` row, not a guessable password:
paying it per poll buys nothing.

These tests pin both halves of the trade. The speedup: a correct secret is checked once per stored
hash. The boundary: rotation and clearing invalidate the memo exactly (it is bound to the stored hash,
never to a clock), and a rejected secret is never memoised, so a guesser keeps paying the KDF.
"""

from __future__ import annotations

import pytest

from auth import storage


@pytest.fixture(autouse = True)
def isolated_auth_db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "auth.db")
    monkeypatch.setattr(storage, "_BOOTSTRAP_PW_PATH", tmp_path / ".bootstrap_password")
    monkeypatch.setattr(storage, "_bootstrap_password", None)
    monkeypatch.setattr(storage, "_api_key_pbkdf2_salt_cache", None)
    monkeypatch.setattr(storage, "_credential_encryption_key_cache", None)
    with storage._desktop_secret_hash_cache_lock:
        storage._desktop_secret_hash_cache.clear()
    yield
    with storage._desktop_secret_hash_cache_lock:
        storage._desktop_secret_hash_cache.clear()


@pytest.fixture
def kdf_calls(monkeypatch):
    """Count real PBKDF2 derivations without changing their result."""
    calls: list[str] = []
    real = storage._pbkdf2_desktop_secret

    def counting(raw_secret: str) -> str:
        calls.append(raw_secret)
        return real(raw_secret)

    monkeypatch.setattr(storage, "_pbkdf2_desktop_secret", counting)
    return calls


def test_a_correct_secret_pays_the_kdf_once_and_then_memoises(kdf_calls):
    secret = storage.create_desktop_secret()
    kdf_calls.clear()

    assert storage.validate_desktop_secret(secret) == storage.DEFAULT_ADMIN_USERNAME
    assert storage.validate_desktop_secret(secret) == storage.DEFAULT_ADMIN_USERNAME
    assert storage.validate_desktop_secret(secret) == storage.DEFAULT_ADMIN_USERNAME

    assert len(kdf_calls) == 1, f"a memoised secret must not re-derive, got {len(kdf_calls)} KDF calls"


def test_the_memoised_path_still_returns_the_current_jwt_secret(kdf_calls):
    """Skipping the KDF must not skip the credential read the caller depends on."""
    secret = storage.create_desktop_secret()
    kdf_calls.clear()  # minting the stored hash is a derivation too; only validation is measured here
    first = storage.validate_desktop_secret_with_credential(secret)
    second = storage.validate_desktop_secret_with_credential(secret)

    assert first is not None and second is not None
    assert first == second
    assert len(kdf_calls) == 1


def test_a_wrong_secret_is_never_memoised(kdf_calls):
    """The KDF is the cost a guesser pays; caching a rejection would hand them a free retry."""
    secret = storage.create_desktop_secret()
    wrong = secret[:-1] + ("A" if secret[-1] != "A" else "B")
    kdf_calls.clear()

    assert storage.validate_desktop_secret(wrong) is None
    assert storage.validate_desktop_secret(wrong) is None

    assert len(kdf_calls) == 2, "a rejected secret must be re-derived on every attempt"


def test_rotating_the_secret_invalidates_the_memo(kdf_calls):
    old = storage.create_desktop_secret()
    assert storage.validate_desktop_secret(old) == storage.DEFAULT_ADMIN_USERNAME

    new = storage.create_desktop_secret()
    kdf_calls.clear()

    assert storage.validate_desktop_secret(old) is None, "a rotated-out secret must be refused"
    assert storage.validate_desktop_secret(new) == storage.DEFAULT_ADMIN_USERNAME
    # The old secret's cached hash no longer equals the stored one, so it is re-derived and rejected;
    # the new one is derived once and memoised.
    assert kdf_calls.count(old) == 1
    assert kdf_calls.count(new) == 1


def test_clearing_the_secret_refuses_the_old_one_through_the_memo(kdf_calls):
    secret = storage.create_desktop_secret()
    assert storage.validate_desktop_secret(secret) == storage.DEFAULT_ADMIN_USERNAME

    storage.clear_desktop_secret()
    assert storage.validate_desktop_secret(secret) is None


def test_the_memo_never_holds_more_than_its_bound(kdf_calls):
    """Rotation leaves the previous secret's id behind; the cache must stay bounded."""
    storage.create_desktop_secret()
    for _ in range(storage._DESKTOP_SECRET_HASH_CACHE_MAX + 4):
        secret = storage.create_desktop_secret()
        assert storage.validate_desktop_secret(secret) == storage.DEFAULT_ADMIN_USERNAME
    with storage._desktop_secret_hash_cache_lock:
        assert len(storage._desktop_secret_hash_cache) <= storage._DESKTOP_SECRET_HASH_CACHE_MAX
