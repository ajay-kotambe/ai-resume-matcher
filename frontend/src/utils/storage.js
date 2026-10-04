/** Tiny storage helpers (auth tokens, cached results, UI preferences). */

function createStore(resolve) {
  return {
    get(key, fallback = null) {
      try {
        const raw = resolve().getItem(key)
        return raw === null ? fallback : JSON.parse(raw)
      } catch {
        return fallback
      }
    },
    set(key, value) {
      try {
        resolve().setItem(key, JSON.stringify(value))
      } catch {
        /* quota or private mode - ignore */
      }
    },
    remove(key) {
      try {
        resolve().removeItem(key)
      } catch {
        /* ignore */
      }
    },
  }
}

/** Persists across sessions. */
export const storage = createStore(() => window.localStorage)

/** Cleared when the tab closes - right scope for "remember for this session". */
export const session = createStore(() => window.sessionStorage)

export default storage