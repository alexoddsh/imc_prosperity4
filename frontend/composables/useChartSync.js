// Module-level singleton — all chart instances share one time-range pub/sub
const handlers = new Set()
let syncing = false

export const useChartSync = () => ({
  subscribe (fn) {
    handlers.add(fn)
    return () => handlers.delete(fn)
  },
  broadcast (source, range) {
    if (syncing || !range) return
    syncing = true
    handlers.forEach(fn => fn !== source && fn(range))
    syncing = false
  }
})
