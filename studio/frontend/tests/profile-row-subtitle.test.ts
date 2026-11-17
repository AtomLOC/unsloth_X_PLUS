// SPDX-License-Identifier: AGPL-3.0-only
// Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

// Council round 3, HIERARCHY: "the footer identity renders `x-` over a faint `x-`".
//
// The profile row's second line was the literal string "X-", and the owner's display title is also
// "X-" (`loginDisplayName` maps the reserved owner id to the product mark), so the row read the same
// mark twice, once bold and once faint. It now shows the login id only when it says something the
// title does not, so the owner's row has one line and a managed account still sees its own name.
//
// The assertions are structural on purpose: the bug was a hard-coded label, so re-introducing one is
// exactly what should fail.

import assert from "node:assert/strict";
import test from "node:test";

import { readSrc } from "./helpers/kit.ts";

const SIDEBAR = readSrc("components/app-sidebar.tsx");

function profileRow(): string {
  const start = SIDEBAR.indexOf('className="sidebar-nav-btn app-user-trigger');
  assert.ok(start > 0, "the profile row moved: re-anchor this test rather than deleting it");
  return SIDEBAR.slice(start, SIDEBAR.indexOf("</SidebarMenuButton>", start));
}

test("the profile row does not print the product mark as a subtitle", () => {
  const row = profileRow();

  assert.doesNotMatch(
    row,
    />\s*X-\s*</,
    "a literal X- subtitle duplicates the owner's title again; use the login id instead",
  );
});

test("the subtitle is shown only when it differs from the title", () => {
  const row = profileRow();

  assert.match(row, /accountSubtitle/, "the row must derive the subtitle, not hard-code one");
  assert.match(
    row,
    /accountSubtitle\s*&&\s*accountSubtitle\s*!==\s*displayTitle/,
    "without the inequality the owner sees the same label twice",
  );
});

test("the subtitle comes from the same login-id helper every other surface uses", () => {
  assert.match(SIDEBAR, /import \{[^}]*loginDisplayName[^}]*\} from "@\/features\/profile"/);
  assert.match(SIDEBAR, /const accountSubtitle = loginDisplayName\(sessionSub\)/);
});
