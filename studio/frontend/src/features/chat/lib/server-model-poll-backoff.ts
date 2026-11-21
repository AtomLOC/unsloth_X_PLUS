// The cadence of the mount-time "catch a load started outside the app" loop.
//
// `waitForServerModel` exists because a load can start behind the UI's back (a CLI `unsloth studio`
// run, a second window). It used to poll /api/inference/status every 500 ms for the whole 60 s idle
// window: 120 requests per page view that never had a load in it, measured at 2.2 requests/s with a
// 524 ms median gap on /hub. Nothing about that window needs a 500 ms grid before something is
// actually loading, so the cadence backs off while nothing is happening and snaps back the moment a
// load appears. The window itself is unchanged: a CLI load is still picked up within 4 s at worst.

/** Delays used while nothing has been seen loading, indexed by how many polls have already run. */
export const IDLE_POLL_DELAYS_MS = [
  500, 500, 1000, 1000, 2000, 2000, 4000,
] as const;

/** Delays used while a load is in flight: a progress-bearing status read, so keep it responsive. */
export const LOADING_POLL_DELAY_MS = 500;

/**
 * How long to wait before the next status poll.
 *
 * @param pollsTaken polls already completed in this wait (0 before the first)
 * @param sawLoad whether any poll has reported a load in flight
 */
export function serverModelPollDelayMs(
  pollsTaken: number,
  sawLoad: boolean,
): number {
  if (sawLoad) return LOADING_POLL_DELAY_MS;
  const index = Math.min(
    Math.max(0, Math.trunc(pollsTaken)),
    IDLE_POLL_DELAYS_MS.length - 1,
  );
  return IDLE_POLL_DELAYS_MS[index];
}
