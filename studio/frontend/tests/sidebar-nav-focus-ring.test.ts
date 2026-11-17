// SPDX-License-Identifier: AGPL-3.0-only
// Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

// Council round 1, A11Y. Measured on the built app: every sidebar tab stop reported
// `outline: none` with no visible shadow, because the generic focus rule only removes the
// browser outline and the nav rows carry no focus-visible ring utility. The composer pills
// already had the shell's one keyboard ring; the nav rows did not. These assertions pin the
// rule, and the pointer-modality exemption that keeps a click from drawing it.

import assert from "node:assert/strict";
import test from "node:test";

import { readSrc } from "./helpers/kit.ts";

const CSS = readSrc("index.css");

test("a sidebar nav row draws the shell's keyboard ring", () => {
  const rule = /\.sidebar-nav-btn:focus-visible\s*\{([^}]*)\}/.exec(CSS);
  assert.ok(rule, "no .sidebar-nav-btn:focus-visible rule: tabbing the sidebar is invisible again");
  assert.match(rule[1], /box-shadow:\s*var\(--x-focus-ring\)/, "the ring must be the one shared token");
  assert.match(rule[1], /outline:\s*none/, "no browser outline in addition to the ring");
});

test("the ring is the same token the composer pills use, not a second look", () => {
  const pill = /\.composer-pill-btn:focus-visible,[\s\S]*?\{([^}]*)\}/.exec(CSS);
  assert.ok(pill, "the composer pill's keyboard ring rule disappeared");
  assert.match(pill[1], /--ring-soft|--x-focus-ring/, "the pills must keep a keyboard ring");
});

test("pointer focus does not draw the nav ring", () => {
  assert.match(
    CSS,
    /html\[data-input-modality="pointer"\]\s*\.sidebar-nav-btn:focus-visible\s*\{\s*box-shadow:\s*none;/,
    "a click, or a menu handing focus back, must not paint a keyboard ring",
  );
});
