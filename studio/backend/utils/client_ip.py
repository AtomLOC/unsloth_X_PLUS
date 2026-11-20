# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

"""Resolve the caller's IP for rate limiting and every other per-client decision.

This module is the ONE place that decides who a caller is. Login buckets, the shared
credential lockout, the token throttle and the endpoint reachability checks all import
``client_ip``; nothing else may re-derive a client address, or one path can be evaded by
taking another.

The rule, in order:

  1. If the operator opts in via ``UNSLOTH_STUDIO_TRUST_FORWARDED`` (Unsloth behind their own
     reverse proxy), resolve the forwarded chain -- ``X-Forwarded-For`` first, then the RFC 7239
     ``Forwarded`` ``for=`` token, by exactly the same rules -- to its *rightmost untrusted hop*:
     walk the hops from the proxy end (right) toward the client end (left) and take the first hop
     that is not an address inside the deployment's own network (loopback, link-local, RFC 1918,
     IPv6 ULA). If every hop is internal, take the rightmost one, which is the hop the proxy
     appended.
  2. If the socket peer is loopback, honor ``CF-Connecting-IP``. Unsloth's managed Cloudflare
     tunnel terminates at 127.0.0.1, so every tunneled visitor would otherwise collapse onto the
     same socket peer (the local cloudflared process) and share one rate-limit bucket.
     ``CF-Connecting-IP`` is set by Cloudflare's edge and can't be forged by a tunneled client.
  3. Otherwise the socket peer, so a direct LAN caller can't spoof a header to dodge a per-IP
     limit.

Why the rightmost *untrusted* hop rather than the leftmost or the bare rightmost one:

  * ``X-Forwarded-For`` / ``Forwarded`` arrive client-controlled. A caller may prepend any
    number of hops; it cannot append after the entry the trusted proxy adds (a proxy that
    overwrites instead of appending simply leaves one entry). So every entry to the LEFT of the
    proxy's own append is attacker-chosen, and the leftmost entry is pure fiction -- the old
    ``routes.auth`` rule keyed login buckets on exactly that value, while ``utils.client_ip``
    keyed the shared lockout on the rightmost hop, so behind an appending proxy the two
    throttles attributed one request to two different clients: an attacker could evade either
    bucket by taking the other path, and an innocent client could inherit a stranger's lockout.
  * Taking the bare rightmost hop fixes that but mis-attributes every deployment whose proxy
    appends a hop on an internal address (the overwhelmingly common ``proxy -> LAN peer``
    layout): the rightmost entry is then the proxy itself, so every client would share it.
  * Walking in from the right and stopping at the first hop that is NOT on the deployment's own
    network yields the closest externally-visible client the chain can attest. A spoofed
    leftmost hop can never win while any non-internal hop sits to its right. The one case a
    spoof still moves the key is when the real client is itself on an internal address and the
    attacker prepends a public one -- that is deliberate: those callers are already inside the
    deployment's network, where address-keyed throttling is approximate anyway, and refusing the
    public hop would collapse every LAN/tunnel client onto the proxy's address instead.
"""

from __future__ import annotations

import ipaddress
import os
import re
from urllib.parse import urlparse

_TRUST_FORWARDED_ENV = "UNSLOTH_STUDIO_TRUST_FORWARDED"

# Networks that only the host or its own LAN can be reached from: a hop inside one of these is one
# of the deployment's proxies (cloudflared, nginx, a LAN ingress), not the visitor they relay.
_INTERNAL_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)


def _trust_forwarded_for() -> bool:
    return os.environ.get(_TRUST_FORWARDED_ENV, "").strip().lower() in {"1", "true", "yes"}


def trust_forwarded_headers() -> bool:
    return _trust_forwarded_for()


def _is_loopback(host: str | None) -> bool:
    try:
        return bool(host) and ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _as_ip(host: str | None):
    """An ``ipaddress`` object, unwrapping the IPv4-mapped IPv6 form, or ``None``."""
    try:
        ip = ipaddress.ip_address(host)
    except (TypeError, ValueError):
        return None
    mapped = getattr(ip, "ipv4_mapped", None)
    return mapped if mapped is not None else ip


def _is_internal_hop(host: str) -> bool:
    """True for an address on the host or its LAN: a proxy hop, never an external visitor."""
    ip = _as_ip(host)
    if ip is None:
        return False
    if ip.is_loopback or ip.is_link_local or ip.is_unspecified:
        return True
    return any(ip.version == network.version and ip in network for network in _INTERNAL_NETWORKS)


def _normalize_addr(value: str | None) -> str | None:
    """Parse one forwarded hop into a bare, validated IP (strip quotes/brackets/port).

    Shared by ``X-Forwarded-For`` entries, ``Forwarded`` ``for=`` values and
    ``CF-Connecting-IP`` so the three can't disagree about what an address is.
    """
    raw = (value or "").strip().strip('"').strip()
    if not raw or raw.lower() == "unknown":
        return None
    if raw.startswith("["):
        # Bracketed IPv6, optionally with a port.
        end = raw.find("]")
        if end <= 0:
            return None
        raw = raw[1:end]
    elif raw.count(":") == 1:
        # IPv4:port. A bare IPv6 has several colons, so it never lands here.
        head, _, tail = raw.rpartition(":")
        if tail.isdigit() and head:
            raw = head
    try:
        return ipaddress.ip_address(raw).compressed
    except ValueError:
        return None


def _hops_from_xff(header: str | None) -> list[str]:
    hops: list[str] = []
    for entry in (header or "").split(","):
        hop = _normalize_addr(entry)
        if hop:
            hops.append(hop)
    return hops


def _hops_from_forwarded(header: str | None) -> list[str]:
    """The ``for=`` values of an RFC 7239 ``Forwarded`` header, in header order."""
    hops: list[str] = []
    for element in (header or "").split(","):
        for token in element.split(";"):
            key, sep, value = token.strip().partition("=")
            if sep and key.strip().lower() == "for":
                hop = _normalize_addr(value)
                if hop:
                    hops.append(hop)
                break
    return hops


def _rightmost_untrusted_hop(hops: list[str]) -> str | None:
    """Rightmost hop that isn't one of our own proxies; else the rightmost hop (proxy-appended)."""
    for hop in reversed(hops):
        if not _is_internal_hop(hop):
            return hop
    return hops[-1] if hops else None


def header_fields(headers, name: str) -> str:
    """All fields of a repeated header, comma-joined (``get`` returns only the first; HAProxy appends a field)."""
    getlist = getattr(headers, "getlist", None)
    if getlist is not None:
        return ",".join(getlist(name))
    return headers.get(name, "") or ""


def client_ip(request) -> str:
    """Best-effort client IP, or ``"_unknown"`` when it can't be determined.

    This is the only client-address resolution in the backend; see the module docstring for the
    trust model and why the rightmost untrusted hop is the one that can't be spoofed.
    """
    if request is None:
        return "_unknown"
    peer = request.client.host if request.client else None
    if _trust_forwarded_for():
        # Every field of a repeated header, not just the first: HAProxy appends one.
        resolved = _rightmost_untrusted_hop(
            _hops_from_xff(header_fields(request.headers, "x-forwarded-for"))
        )
        if resolved is None:
            resolved = _rightmost_untrusted_hop(
                _hops_from_forwarded(header_fields(request.headers, "forwarded"))
            )
        if resolved:
            return resolved
    if _is_loopback(peer):
        if request_from_managed_tunnel(
            getattr(request, "scope", None), _request_app_state(request)
        ):
            cf = _normalize_addr(request.headers.get("cf-connecting-ip"))
            if cf:
                return cf
        if names_a_forwarded_client(request):
            return f"relayed:{peer}"
    return peer or "_unknown"


def _request_app_state(request):
    try:
        return request.app.state
    except Exception:
        return None


def _managed_tunnel_hostname(app_state) -> str | None:
    url = getattr(app_state, "cloudflare_url", None) if app_state is not None else None
    if not isinstance(url, str) or not url:
        return None
    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    return host.lower().rstrip(".") if host else None


def request_from_managed_tunnel(scope, app_state) -> bool:
    """Live published tunnel, one valid ``CF-Connecting-IP``, Host naming it. Caller checks the peer is loopback."""
    expected = _managed_tunnel_hostname(app_state)
    if not expected or not isinstance(scope, dict):
        return False
    cf_values = []
    host_values = []
    for name, value in scope.get("headers") or ():
        if name == b"cf-connecting-ip":
            cf_values.append(value)
        elif name == b"host":
            host_values.append(value)
    if len(cf_values) != 1 or len(host_values) != 1:
        return False
    try:
        if _normalize_addr(cf_values[0].decode("latin-1")) is None:
            return False
        request_host = urlparse("//" + host_values[0].decode("latin-1")).hostname
    except (UnicodeDecodeError, ValueError):
        return False
    return bool(request_host) and request_host.lower().rstrip(".") == expected


def _is_loopback_ip(host: str | None) -> bool:
    if not host or "%" in host:  # a scope id (::1%eth0) is never a plain loopback
        return False
    try:
        ip = ipaddress.ip_address(host)
    except (TypeError, ValueError):
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    return ip.is_loopback or (mapped is not None and mapped.is_loopback)


# A loopback peer with these headers is a proxy relaying a remote client.
_PROXIED_CLIENT_HEADERS = (
    "cf-connecting-ip",
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-real-ip",
)


def _host_header_is_loopback(host_header: str | None) -> bool:
    """Raw Host header, so a bad Host cannot fall back to the (loopback) ASGI server address."""
    if not host_header:
        return False
    host = host_header.strip()
    if host.startswith("["):  # [IPv6] or [IPv6]:port
        end = host.find("]")
        if end == -1 or (host[end + 1 :] and not host[end + 1 :].startswith(":")):
            return False  # unclosed bracket or junk after ] (e.g. [::1]evil)
        host = host[1:end]
    elif host.count(":") == 1:  # host:port
        host = host.split(":", 1)[0]
    host = host.lower().rstrip(".")
    return host == "localhost" or _is_loopback_ip(host)


_PROXY_HOSTS_ENV = "UNSLOTH_STUDIO_PROXY_HOSTS"
_DNS_NAME = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)*")


def _authority_hostname(value: str | None) -> str | None:
    host = (value or "").strip().lower()
    if "://" in host:  # tolerate a pasted URL in the setting
        host = host.split("://", 1)[1].split("/", 1)[0]
    if host.count(":") == 1:
        host, port = host.split(":", 1)
        if not port.isdigit():
            return None
    host = host.rstrip(".")
    # Names only: a wildcard would admit any rebound name.
    if host == "localhost" or not _DNS_NAME.fullmatch(host):
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    return None


def trusted_proxy_hosts() -> frozenset[str]:
    raw = os.environ.get(_PROXY_HOSTS_ENV, "")
    names = (_authority_hostname(entry) for entry in raw.replace(",", " ").split())
    return frozenset(name for name in names if name)


def request_via_trusted_proxy(scope) -> bool:
    """Local reverse proxy for an allowlisted name. Host must be loopback or allowlisted: a DNS-rebound page
    sends its own name as Host, so it cannot borrow the allowlist via X-Forwarded-Host."""
    allowed = trusted_proxy_hosts()
    if not allowed or not isinstance(scope, dict):
        return False
    server = scope.get("server")
    client = scope.get("client")
    if not server or not client or not _is_loopback_ip(server[0]):
        return False
    # UNSLOTH_STUDIO_TRUST_FORWARDED makes uvicorn replace the loopback peer with X-Forwarded-For.
    if not _is_loopback_ip(client[0]) and not trust_forwarded_headers():
        return False
    host_values = []
    forwarded_hosts = []
    for name, value in scope.get("headers") or ():
        if name == b"host":
            host_values.append(value.decode("latin-1"))
        elif name == b"x-forwarded-host":
            forwarded_hosts.extend(p for p in value.decode("latin-1").split(",") if p.strip())
    if len(host_values) != 1:
        return False
    host_allowed = _authority_hostname(host_values[0]) in allowed
    if not host_allowed and not _host_header_is_loopback(host_values[0]):
        return False
    if any(_authority_hostname(part) not in allowed for part in forwarded_hosts):
        return False
    return host_allowed or bool(forwarded_hosts)


# Hop headers a proxy adds without naming the client (Apache's X-Forwarded-Server, an nginx block that
# only sets X-Forwarded-Proto). Kept apart because Colab's tolerated-header check walks the tuple above.
_PROXY_HOP_HEADERS = ("via", "x-forwarded-port", "x-forwarded-proto", "x-forwarded-server")


_RELAY_HEADERS = frozenset(_PROXIED_CLIENT_HEADERS + _PROXY_HOP_HEADERS)


def names_a_forwarded_client(request) -> bool:
    """Whether a proxy or tunnel marked this request as relayed."""
    return not _RELAY_HEADERS.isdisjoint(k.lower() for k in request.headers.keys())


def is_direct_local_request(request) -> bool:
    """A direct loopback connection to a loopback Host: not relayed by a proxy or tunnel, not DNS rebinding."""
    client = request.client
    if client is None or not _is_loopback_ip(client.host):
        return False
    if names_a_forwarded_client(request):
        return False
    return _host_header_is_loopback(request.headers.get("host"))
