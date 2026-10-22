/** Coalesce refresh bursts, preserving a trailing load for changes during a fetch. */
export function createRefreshCoordinator(load: () => Promise<void>, delayMs = 75) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let running = false;
  let dirty = false;
  let disposed = false;
  let waiters: Array<{ resolve: () => void; reject: (error: unknown) => void }> = [];

  function settle(error?: unknown) {
    const pending = waiters;
    waiters = [];
    pending.forEach(waiter => error === undefined ? waiter.resolve() : waiter.reject(error));
  }

  function schedule() {
    if (!running && timer === undefined && !disposed) {
      timer = setTimeout(() => { void flush(); }, delayMs);
    }
  }

  async function flush() {
    timer = undefined;
    if (disposed) return;
    running = true;
    dirty = false;
    try {
      await load();
    } catch (error) {
      dirty = false;
      settle(error);
    } finally {
      running = false;
      if (!disposed) {
        if (dirty) schedule();
        else settle();
      }
    }
  }

  return {
    request(): Promise<void> {
      if (disposed) return Promise.resolve();
      dirty = true;
      const pending = new Promise<void>((resolve, reject) => waiters.push({ resolve, reject }));
      schedule();
      return pending;
    },
    cancel() {
      disposed = true;
      if (timer !== undefined) clearTimeout(timer);
      timer = undefined;
      dirty = false;
      settle();
    },
  };
}
