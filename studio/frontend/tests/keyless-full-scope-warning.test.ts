// SPDX-License-Identifier: AGPL-3.0-only
// Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

// SEC-3: keyless `full` scope is a per-machine boundary, not a per-user one.
//
// With `keyless_api_access_scope=full`, any caller that reaches the port over loopback with no
// Origin and no cross-site Sec-Fetch-Site authenticates as the installation owner for every route
// (`utils/keyless_api_access.py:228-241`, `443-464`, `600-629`) -- including shutdown, model
// deletion and remote-access start. There is no OS-user check, so a second local account is
// owner-equivalent while the setting is on. The audit's remediation was to say so in the setting
// itself rather than leave the docstring's `curl`/SDK framing implying "just me".
//
// These assertions pin the wording: the confirmation and the always-visible row both have to name
// the local-account boundary, because the dialog is dismissed after the grant is made.

import assert from "node:assert/strict";
import test from "node:test";

import { readSrc } from "./helpers/kit.ts";

const SECTION = readSrc(
  "features/settings/components/keyless-api-access-section.tsx",
);

function fullGrantBody(): string {
  const start = SECTION.indexOf("  full: {");
  assert.ok(
    start > 0,
    "the `full` grant copy moved: re-anchor this test rather than deleting it",
  );
  return SECTION.slice(start, SECTION.indexOf("  tools: {", start));
}

test("the full-scope confirmation names local user accounts, not just localhost", () => {
  const body = fullGrantBody();

  assert.match(
    body,
    /[Aa]ny user account or process on this machine/,
    "the grant is host-wide; saying only 'localhost callers' understates it",
  );
  assert.match(
    body,
    /per-machine grant, not a per-user one/,
    "the boundary itself has to be stated, not implied",
  );
  assert.match(
    body,
    /another local account gets the same owner-level access/,
    "the concrete consequence is what makes the warning actionable",
  );
});

test("the always-visible row states the same boundary", () => {
  const row = /label="Everything else"\s+description="([^"]+)"/.exec(SECTION);
  assert.ok(row, "the 'Everything else' row lost its description");

  assert.match(
    row[1],
    /any user or process on this machine that reaches localhost/,
    "a user who never opens the confirmation still needs the boundary in front of them",
  );
  assert.match(row[1], /not just to you/);
});

test("the reading of `full` still matches what the backend grants", () => {
  // The copy must not promise a narrowing the code does not do: `/api/shutdown`, model deletion
  // and remote-access start stay reachable, so the wording claims exactly those mutations.
  const body = fullGrantBody();

  assert.match(body, /read, change and delete files and settings/);
  assert.doesNotMatch(body, /only you|just this app|your own account/i);
});
