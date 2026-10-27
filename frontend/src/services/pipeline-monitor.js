const TERMINAL_STATES = new Set(['success', 'failed']);

export const isTerminalRun = (run) => TERMINAL_STATES.has(run?.state);

export const isTemporaryStatusError = (error) => (
  !error.status || [404, 408, 429, 500, 502, 503, 504].includes(error.status)
);

// Read status only. Never submit or retry a pipeline trigger here.
export async function monitorPipeline(runId, {
  fetchStatus,
  onStatus = () => {},
  onWarning = () => {},
  wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  attempts = 150,
  interval = 2000,
}) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const status = await fetchStatus(runId);
      onStatus(status);
      onWarning('');
      if (isTerminalRun(status)) return status;
    } catch (error) {
      if (!isTemporaryStatusError(error)) throw error;
      onWarning('Status temporarily unavailable. The accepted pipeline may still be running; monitoring will retry.');
    }
    if (attempt + 1 < attempts) await wait(interval);
  }
  onWarning('Monitoring paused. Execution is still accepted. Use Refresh to check this same run before starting another pipeline.');
  return null;
}
