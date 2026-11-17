# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

"""Regression pins for two SECURITY_AUDIT entries that were fixed without a test.

SEC-5: `SecurityHeadersMiddleware` compares `scope["path"]`, and uvicorn keeps the `--root-path`
prefix inside `path`. The middleware strips it now, but nothing exercised that, so an edit could
silently drop the `/api/` no-store rule and the framed-shell `X-Frame-Options` exemption behind a
prefixed proxy. These tests drive the middleware directly with a raw ASGI scope whose `path` carries
the prefix, which `TestClient(root_path=...)` cannot produce (it leaves the prefix out of `path`).

SEC-7: `_parse_failure_detail` interpolates a parser exception into a 503/422 detail. The managed
uploads root holds the install layout and the account id, so the reason is redacted before it is
returned. The redaction is the security property, so it is pinned rather than assumed.
"""

from __future__ import annotations

import asyncio

import pytest
from starlette.datastructures import MutableHeaders

REASON = r"[Errno 2] No such file: /home/alice/.unsloth/accounts/acc-123/uploads/paper.pdf"


@pytest.fixture(scope = "module")
def main_module():
    import main as _main  # noqa: F401  (importing is the fixture's job, as in test_middleware.py)

    return _main


async def _run_middleware(main_module, path: str, root_path: str):
    """One request through SecurityHeadersMiddleware over a fake app, returning the headers."""
    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = main_module.SecurityHeadersMiddleware(inner)
    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await middleware(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "root_path": root_path,
            "headers": [],
            "query_string": b"",
        },
        receive,
        send,
    )
    return MutableHeaders(raw = sent[0]["headers"])


def test_api_no_store_survives_a_root_path_prefix(main_module):
    headers = asyncio.run(
        _run_middleware(main_module, "/studio/api/inference/monitor", "/studio")
    )
    assert headers["cache-control"] == "no-store"


def test_the_frame_shell_exemption_survives_a_root_path_prefix(main_module):
    headers = asyncio.run(
        _run_middleware(main_module, "/studio/api/inference/mcp-app-frame", "/studio")
    )
    assert "x-frame-options" not in headers, (
        "a framed shell behind a path prefix got DENY: the prefix was not stripped"
    )


def test_an_ordinary_page_behind_a_prefix_still_gets_deny(main_module):
    """The strip must not turn every path into a shell exemption."""
    headers = asyncio.run(_run_middleware(main_module, "/studio/settings", "/studio"))
    assert headers["x-frame-options"] == "DENY"


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError(REASON),
        ValueError("/Users/alice/Library/Application Support/unsloth/accounts/acc-123/uploads/a.pdf"),
    ],
)
def test_parser_failure_reason_does_not_leak_a_host_path(error):
    from routes.rag import _parse_failure_detail

    detail = _parse_failure_detail("paper.pdf", error)

    assert detail.startswith("paper.pdf could not be read:"), detail
    for leaked in ("/home/alice", "/Users/alice", "accounts", "acc-123", "unsloth"):
        assert leaked not in detail, f"{leaked!r} reached the client: {detail}"
    assert "<path>" in detail, "the reason must stay readable with the path replaced"


def test_a_reason_without_a_path_is_passed_through():
    from routes.rag import _parse_failure_detail

    detail = _parse_failure_detail("paper.pdf", ValueError("unsupported image mode P"))
    assert detail == "paper.pdf could not be read: unsupported image mode P"
