// SPDX-License-Identifier: AGPL-3.0-only
// Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

// Council round 1/2, A11Y: four tab stops had no visible focus indicator on /chat.
//
// The shell strips every focus outline (`index.css`, `button:focus, a:focus, summary:focus,
// [role="button"]:focus { outline: none !important }`), so a control that does not draw its own
// ring is invisible to a keyboard user. Walking 14 real Tab presses on the served build, 4 stops
// reported neither an outline nor a box-shadow: Dictate, the brand/home anchor, "Show workflows"
// (a `.sidebar-row-action`, which also carries `outline-none` and stays at opacity 0 until its row
// is hovered), and the Projects section trigger. After adding the shell's ring to each, the same
// walk reported 14 of 14.
//
// These assertions pin the rule and the four call sites. They are deliberately narrow: a broader
// "every anchor has a ring" check cannot see Tailwind's composed box-shadow and would pass on
// elements whose ring is hidden by a parent's opacity.

import assert from "node:assert/strict";
import test from "node:test";

import { readSrc } from "./helpers/kit.ts";

const CSS = readSrc("index.css");
const SIDEBAR = readSrc("components/app-sidebar.tsx");
const THREAD = readSrc("components/assistant-ui/thread.tsx");

test("the global outline strip is still there, so a ring is genuinely required", () => {
  const rule =
    /button:focus,\s*a:focus,\s*summary:focus,\s*\[role="button"\]:focus\s*\{([^}]*)\}/.exec(
      CSS,
    );
  assert.ok(
    rule,
    "the focus-outline reset moved: re-anchor this test rather than deleting it",
  );
  assert.match(rule[1], /outline:\s*none\s*!important/);
});

test("a sidebar row action reveals itself and draws the ring on keyboard focus", () => {
  const rule = /\.sidebar-row-action:focus-visible\s*\{([^}]*)\}/.exec(CSS);
  assert.ok(
    rule,
    "`.sidebar-row-action:focus-visible` is gone: Show workflows is invisible again",
  );
  assert.match(
    rule[1],
    /box-shadow:\s*0 0 0 2px var\(--ring\)/,
    "same 2px ring the nav rows draw",
  );
  assert.match(
    rule[1],
    /opacity:\s*1/,
    "the action is opacity-0 until its row is hovered",
  );
  assert.match(rule[1], /pointer-events:\s*auto/);
});

test("the brand anchor draws a ring", () => {
  const start = SIDEBAR.indexOf("<Link");
  const anchor = SIDEBAR.slice(
    SIDEBAR.indexOf('to="/chat"'),
    SIDEBAR.indexOf('aria-label={t("shell.aria.home")}'),
  );
  assert.ok(
    start > 0 && anchor.length > 0,
    "the home Link moved: re-anchor this test rather than deleting it",
  );
  assert.match(anchor, /focus-visible:ring-2 focus-visible:ring-ring/);
  assert.match(
    anchor,
    /rounded-md/,
    "a ring around an unrounded wordmark clips oddly",
  );
});

test("every collapsible sidebar section trigger draws a ring", () => {
  const triggers =
    SIDEBAR.match(/<CollapsibleTrigger className="[^"]*"/g) ?? [];
  assert.ok(
    triggers.length >= 4,
    `expected the section triggers, found ${triggers.length}`,
  );

  const ringless = triggers.filter(
    (t) => !/focus-visible:ring-2 focus-visible:ring-ring/.test(t),
  );
  assert.deepEqual(
    ringless,
    [],
    "a section trigger would be a ringless tab stop again",
  );
});

test("the Dictate composer button draws a ring", () => {
  const dictate = /tooltip="Dictate"[\s\S]{0,400}?className="([^"]+)"/.exec(
    THREAD,
  );
  assert.ok(
    dictate,
    "the Dictate button moved: re-anchor this test rather than deleting it",
  );
  assert.match(
    dictate[1],
    /focus-visible:ring-2/,
    "a ghost icon button only changes its border, which is not an indicator",
  );
});
