// Shared worker-liveness constants. The backend heartbeat is a fixed 60 s
// (backend/worker.py HEARTBEAT_INTERVAL), independent of the user's check_interval,
// so the offline threshold must not scale with check_interval either.
export const HEARTBEAT_INTERVAL_MS = 60_000;
export const HEARTBEAT_TIMEOUT_MS = 90_000;
