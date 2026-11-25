// The idle backoff behind the mount-time status poll.
//
// `/api/inference/status` was requested 22 times in 10 s (2.2/s, median gap 524 ms) on /hub with
// nothing loading: `waitForServerModel` polled every 500 ms for its whole 60 s idle window. These
// tests pin the replacement cadence, and pin that the window itself did not shrink: a CLI load must
// still be picked up as fast as before whenever it starts.

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  IDLE_POLL_DELAYS_MS,
  LOADING_POLL_DELAY_MS,
  serverModelPollDelayMs,
} from "../src/features/chat/lib/server-model-poll-backoff.ts";

test("an idle wait backs off instead of asking twice a second", () => {
  const delays = Array.from({ length: 12 }, (_, i) =>
    serverModelPollDelayMs(i, false),
  );

  assert.deepEqual(
    delays.slice(0, 3),
    [500, 500, 1000],
    "the first seconds stay responsive",
  );
  assert.ok(
    delays.every((d, i) => i === 0 || d >= delays[i - 1]),
    `delays must not speed up: ${delays}`,
  );
  assert.equal(delays.at(-1), 4000, "and settle at the slowest step");
});

test("the whole idle window costs a fraction of the old 500 ms grid", () => {
  // Replay the loop: 60 s of wall clock, taking each delay before the next poll.
  let elapsed = 0;
  let polls = 0;
  while (elapsed < 60_000) {
    elapsed += serverModelPollDelayMs(polls, false);
    polls += 1;
  }

  assert.ok(
    polls <= 25,
    `60 s idle should cost at most 25 requests, cost ${polls}`,
  );
  assert.ok(
    polls >= 15,
    `but it must still re-check periodically, cost only ${polls}`,
  );
});

test("a load in flight keeps the fast cadence", () => {
  for (const polls of [0, 1, 5, 500]) {
    assert.equal(serverModelPollDelayMs(polls, true), LOADING_POLL_DELAY_MS);
  }
  assert.equal(LOADING_POLL_DELAY_MS, 500);
});

test("a load is still noticed within four seconds of it starting", () => {
  // Worst case: the load begins right after a poll at the slowest step.
  assert.ok(
    serverModelPollDelayMs(IDLE_POLL_DELAYS_MS.length - 1, false) <= 4000,
  );
});

test("poll counts outside the table clamp instead of returning undefined", () => {
  assert.equal(serverModelPollDelayMs(-3, false), IDLE_POLL_DELAYS_MS[0]);
  assert.equal(serverModelPollDelayMs(1e9, false), IDLE_POLL_DELAYS_MS.at(-1));
  assert.equal(serverModelPollDelayMs(2.7, false), IDLE_POLL_DELAYS_MS[2]);
});
