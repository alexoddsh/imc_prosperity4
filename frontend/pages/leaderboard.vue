<template>
  <div style="padding: 16px; font-family: 'IBM Plex Mono', monospace; font-size: 12px;">
    <h2 style="margin: 0 0 12px; font-size: 14px; font-weight: 600;">leaderboard</h2>

    <div style="margin-bottom: 8px; color: #999;">
      sorted by total pnl — {{ runs.length }} runs
    </div>

    <!-- tooltip -->
    <div
      v-if="tooltip.run"
      :style="{
        position: 'fixed',
        left: tooltip.x + 14 + 'px',
        top: tooltip.y + 14 + 'px',
        background: '#111',
        color: '#eee',
        border: '1px solid #333',
        padding: '8px 10px',
        fontSize: '11px',
        pointerEvents: 'none',
        zIndex: 9999,
        minWidth: '160px',
        lineHeight: '1.7',
      }"
    >
      <div style="color: #888; margin-bottom: 4px; font-size: 10px;">{{ fmt(tooltip.run.created_at) }}</div>
      <div
        v-for="(pnl, product) in tooltip.run.products_pnl"
        :key="product"
        style="display: flex; justify-content: space-between; gap: 16px;"
      >
        <span style="color: #aaa; text-transform: uppercase; font-size: 10px;">{{ product }}</span>
        <span :style="{ color: pnl >= 0 ? '#00aa44' : '#de0404' }">{{ fmt_pnl(pnl) }}</span>
      </div>
      <div v-if="!tooltip.run.products_pnl || !Object.keys(tooltip.run.products_pnl).length" style="color: #555;">no product data</div>
    </div>

    <table style="width: 100%; border-collapse: collapse;">
      <thead>
        <tr style="border-bottom: 1px solid #ccc; color: #999;">
          <th style="text-align: left; padding: 4px 8px;">#</th>
          <th style="text-align: left; padding: 4px 8px; color: #bbb;">id</th>
          <th style="text-align: left; padding: 4px 8px;">algo</th>
          <th style="text-align: left; padding: 4px 8px;">dev</th>
          <th style="text-align: left; padding: 4px 8px;">round</th>
          <th style="text-align: right; padding: 4px 8px;">pnl</th>
          <th style="text-align: left; padding: 4px 8px;">status</th>
          <th style="text-align: left; padding: 4px 8px;">created</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(run, i) in sortedRuns"
          :key="run.id"
          style="border-bottom: 1px solid #eee; cursor: pointer;"
          @click="$router.push({ path: '/', query: { taskId: run.id } })"
        >
          <td style="padding: 4px 8px; color: #999;">{{ i + 1 }}</td>
          <td style="padding: 4px 8px; color: #bbb; font-size: 10px;">{{ run.id.slice(0, 6) }}</td>
          <td
            style="padding: 4px 8px; position: relative;"
            @mouseenter="(e) => showTooltip(e, run)"
            @mousemove="(e) => moveTooltip(e)"
            @mouseleave="hideTooltip"
          >{{ run.algo_name }}</td>
          <td style="padding: 4px 8px;"><p class="badge">{{ run.dev }}</p></td>
          <td style="padding: 4px 8px;">{{ run.round_id }}</td>
          <td style="padding: 4px 8px; text-align: right;" :style="{ color: run.total_pnl >= 0 ? '#00aa44' : '#de0404' }">
            {{ fmt_pnl(run.total_pnl) }}
          </td>
          <td style="padding: 4px 8px; color: #999;">{{ run.status }}</td>
          <td style="padding: 4px 8px; color: #999;">{{ fmt(run.created_at) }}</td>
        </tr>
      </tbody>
    </table>

    <div v-if="!runs.length" style="color: #999; margin-top: 12px;">no runs found</div>

    <!-- per-product top-5 grid -->
    <div v-if="products.length" style="margin-top: 28px;">
      <div style="margin-bottom: 12px; font-size: 13px; font-weight: 600;">by product</div>
      <div style="display: flex; flex-wrap: wrap; gap: 16px;">
        <div
          v-for="product in products"
          :key="product"
          style="border: 1px solid #ddd; padding: 10px 12px; min-width: 220px; flex: 1 1 220px;"
        >
          <div style="font-weight: 600; margin-bottom: 8px; font-size: 11px; color: #555; letter-spacing: 0.05em; text-transform: uppercase;">
            {{ product }}
          </div>
          <table style="width: 100%; border-collapse: collapse;">
            <tbody>
              <tr
                v-for="(entry, i) in top5(product)"
                :key="entry.id"
                style="cursor: pointer;"
                @click="$router.push({ path: '/', query: { taskId: entry.id } })"
              >
                <td style="padding: 3px 4px; color: #bbb; width: 18px;">{{ i + 1 }}</td>
                <td style="padding: 3px 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 130px;">{{ entry.algo_name }} || {{ entry.id }}</td>
                <td style="padding: 3px 4px; text-align: right;" :style="{ color: entry.pnl >= 0 ? '#00aa44' : '#de0404' }">
                  {{ fmt_pnl(entry.pnl) }}
                </td>
              </tr>
              <tr v-if="!top5(product).length">
                <td colspan="3" style="color: #bbb; padding: 3px 4px;">no data</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const supabase = useSupabaseClient()
const runs = ref([])

const tooltip = ref({ run: null, x: 0, y: 0 })
const showTooltip = (e, run) => { tooltip.value = { run, x: e.clientX, y: e.clientY } }
const moveTooltip = (e) => { tooltip.value.x = e.clientX; tooltip.value.y = e.clientY }
const hideTooltip = () => { tooltip.value.run = null }

onMounted(async () => {
  const { data } = await supabase
    .from('backtest_runs')
    .select('id, algo_name, dev, round_id, status, total_pnl, products_pnl, created_at')
    .neq('status', 'FAILED')
    .order('created_at', { ascending: false })
  if (data) runs.value = data
})

const sortedRuns = computed(() =>
  [...runs.value]
    .filter(r => r.total_pnl != null)
    .sort((a, b) => b.total_pnl - a.total_pnl)
    .concat(runs.value.filter(r => r.total_pnl == null))
    .slice(0, 20)
)

const products = computed(() => {
  const seen = new Set()
  for (const run of runs.value) {
    const pnls = run.products_pnl
    if (pnls && typeof pnls === 'object') {
      for (const k of Object.keys(pnls)) seen.add(k)
    }
  }
  return [...seen].sort()
})

const top5 = (product) =>
  runs.value
    .filter(r => r.products_pnl && r.products_pnl[product] != null)
    .map(r => ({ id: r.id, algo_name: r.algo_name, pnl: r.products_pnl[product] }))
    .sort((a, b) => b.pnl - a.pnl)
    .slice(0, 5)

const fmt_pnl = (v) =>
  v != null ? v.toLocaleString('en-US', { maximumFractionDigits: 0 }) : '—'

const fmt = (ts) => {
  if (!ts) return '—'
  const d = new Date(ts)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}
</script>
