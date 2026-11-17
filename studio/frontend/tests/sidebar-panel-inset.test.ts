// SPDX-License-Identifier: AGPL-3.0-only
// Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

// The macOS-style glass shell is supposed to be two floating panels with the same 12px inset.
//
// It was not: the sidebar carried `size-full` from shadcn (width/height 100%) and a utilities-layer
// utility beats the components-layer geometry below it, so `height: calc(100% - 24px)` never applied.
// The panel was the container's full height PLUS a 12px top margin. Measured in the served build at a
// 900px viewport: sidebar bottom 912, content panel bottom 888 -- the sidebar hung 12px past the
// window edge with its bottom corner clipped, and both review panels saw it (one as H, one as C).
//
// With `!important` on the two length declarations the measurement is 888 / 888. These assertions
// pin the declarations that make the inset real, and the pairing with the content panel, because a
// bare `calc()` here reads correct and does nothing.

import assert from "node:assert/strict";
import test from "node:test";

import { readSrc } from "./helpers/kit.ts";

const CSS = readSrc("index.css");

function sidebarRule(): string {
  const start = CSS.indexOf('.dark [data-sidebar="sidebar"] {');
  assert.ok(
    start > 0,
    "the glass sidebar rule moved: re-anchor this test rather than deleting it",
  );
  const end = CSS.indexOf("}", start);
  return CSS.slice(start, end);
}

test("the sidebar panel's inset geometry outranks the size-full utility", () => {
  const rule = sidebarRule();

  assert.match(rule, /margin:\s*12px/);
  assert.match(
    rule,
    /height:\s*calc\(100% - 24px\)\s*!important/,
    "without !important the utility wins and the panel overhangs the window bottom by 12px",
  );
  assert.match(rule, /width:\s*calc\(100% - 24px\)\s*!important/);
});

test("the content panel uses the same 12px inset on the bottom edge", () => {
  const start = CSS.indexOf('.dark [data-slot="sidebar-inset"] {');
  assert.ok(start > 0, "the glass content rule moved: re-anchor this test");
  const rule = CSS.slice(start, CSS.indexOf("}", start));

  assert.match(
    rule,
    /margin:\s*12px 12px 12px 0/,
    "the two panels must agree on the bottom inset or the shell looks crooked",
  );
});
