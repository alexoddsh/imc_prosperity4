<template>
  <div style="padding: 16px; font-family: 'IBM Plex Mono', monospace; font-size: 12px;">
    <h2 style="margin: 0 0 12px; font-size: 14px; font-weight: 600;">leaderboard</h2>

    <div style="margin-bottom: 8px; color: #999;">
      sorted by total pnl — {{ runs.length }} runs
    </div>

    <table style="width: 100%; border-collapse: collapse;">
      <thead>
        <tr style="border-bottom: 1px solid #ccc; color: #999;">
          <th style="text-align: left; padding: 4px 8px;">#</th>
          <th style="text-align: left; padding: 4px 8px;">algo</th>
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
          <td style="padding: 4px 8px;">{{ run.algo_name }}</td>
          <td style="padding: 4px 8px;">{{ run.round_id }}</td>
          <td style="padding: 4px 8px; text-align: right;" :style="{ color: run.total_pnl >= 0 ? '#00aa44' : '#de0404' }">
            {{ run.total_pnl != null ? run.total_pnl.toFixed(0) : '—' }}
          </td>
          <td style="padding: 4px 8px; color: #999;">{{ run.status }}</td>
          <td style="padding: 4px 8px; color: #999;">{{ fmt(run.created_at) }}</td>
        </tr>
      </tbody>
    </table>

    <div v-if="!runs.length" style="color: #999; margin-top: 12px;">no runs found</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const supabase = useSupabaseClient()
const runs = ref([])

onMounted(async () => {
  const { data } = await supabase
    .from('backtest_runs')
    .select('id, algo_name, round_id, status, total_pnl, created_at')
    .order('created_at', { ascending: false })
  if (data) runs.value = data
})

const sortedRuns = computed(() =>
  [...runs.value]
    .filter(r => r.total_pnl != null)
    .sort((a, b) => b.total_pnl - a.total_pnl)
    .concat(runs.value.filter(r => r.total_pnl == null))
)

const fmt = (ts) => {
  if (!ts) return '—'
  const d = new Date(ts)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}
</script>
