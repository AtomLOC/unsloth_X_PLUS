// SPDX-License-Identifier: AGPL-3.0-only
// Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

// Council round 2, STATES: "the skeleton loads announce nothing".
//
// The placeholder rows are deliberately `aria-hidden` -- announcing ten pulsing rectangles is worse
// than silence -- but the loading *state* then had no announcement at all, so a screen reader was
// told nothing while the catalogue or the library was arriving. Each loading container now carries a
// sibling `role="status"` line with the shared "Loading..." string, and the decorative rows stay
// hidden.
//
// Measured on the served build (`.council/round-2/loading-announcements.json`): at +600 ms the Hub
// showed 39 skeletons and announced `status: "Loading..."`; the Library loads faster than the sample
// and never showed its grid, so that path is pinned by source here instead of by observation.

import assert from "node:assert/strict";
import test from "node:test";

import { readSrc } from "./helpers/kit.ts";

const HUB = readSrc("features/hub/catalog/catalog-states.tsx");
const LIBRARY = readSrc("features/library/library-page.tsx");

function skeletonList(): string {
  const start = HUB.indexOf("export function SkeletonList");
  assert.ok(start > 0, "SkeletonList moved: re-anchor this test rather than deleting it");
  return HUB.slice(start, HUB.indexOf("export function", start + 10));
}

function loadingGrid(): string {
  const start = LIBRARY.indexOf("function LoadingGrid()");
  assert.ok(start > 0, "LoadingGrid moved: re-anchor this test rather than deleting it");
  return LIBRARY.slice(start, LIBRARY.indexOf("const FILE_TYPES", start));
}

test("the hub catalogue announces that it is loading", () => {
  const block = skeletonList();

  assert.match(block, /role="status"/, "no status region: the loading state is silent");
  assert.match(block, /aria-live="polite"/);
  assert.match(block, /t\("common\.loading"\)/, "reuse the shared string, not a new one");
});

test("the hub's placeholder rows stay hidden from assistive tech", () => {
  const block = skeletonList();

  assert.match(
    block,
    /<ul[^>]*aria-hidden="true"/,
    "the rows are decoration; announcing them would read as ten empty items",
  );
  // The announcement must be a sibling of the hidden list, not inside it.
  const statusAt = block.indexOf('role="status"');
  const listAt = block.indexOf("<ul");
  assert.ok(statusAt > 0 && statusAt < listAt, "the status line sits outside the aria-hidden list");
});

test("the library grid announces and keeps its tiles hidden", () => {
  const block = loadingGrid();

  assert.match(block, /role="status"/);
  assert.match(block, /aria-live="polite"/);
  assert.match(block, /t\("common\.loading"\)/);
  assert.match(block, /aria-hidden="true"/, "the tile grid is decoration");
});
