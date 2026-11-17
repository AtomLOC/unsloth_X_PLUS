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
  assert.match(rule[1], /box-shadow:\s*0 0 0 2px var\(--ring\)/, "the ring must match the nav submenu rows (ring-2 ring-ring)");
  assert.match(rule[1], /outline:\s*none/, "no browser outline in addition to the ring");
});

test("the ring is the same one the nav's own submenu rows draw", () => {
  // app-sidebar.tsx's workflow rows already carry `focus-visible:ring-2 focus-visible:ring-ring`;
  // the plain nav rows were the odd ones out. Two keyboard looks in one sidebar is the defect.
  assert.match(
    readSrc("components/app-sidebar.tsx"),
    /focus-visible:ring-2 focus-visible:ring-ring/,
    "the sibling nav control's ring changed; keep .sidebar-nav-btn in step with it",
  );
});

test("pointer focus does not draw the nav ring", () => {
  assert.match(
    CSS,
    /html\[data-input-modality="pointer"\]\s*\.sidebar-nav-btn:focus-visible\s*\{\s*box-shadow:\s*none;/,
    "a click, or a menu handing focus back, must not paint a keyboard ring",
  );
});
