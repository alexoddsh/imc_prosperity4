<template>
  <div style="height: 100%; width: 100%;">
    <client-only>
      <apexchart type="area" height="100%" :options="chartOptions" :series="chartSeries" />
    </client-only>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
const props = defineProps(['taskId', 'product'])
const supabase = useSupabaseClient()

const chartSeries = ref([])
const chartOptions = ref({
  chart: { id: 'sync-pos', group: 'backtest-sync', animations: { enabled: false }, toolbar: { show: false }, sparkline: { enabled: false } },
  colors: ['#000000'],
  stroke: { curve: 'stepline', width: 1.5 },
  fill: { type: 'solid', opacity: 0.1, colors: ['#FF8C00'] },
  xaxis: { type: 'numeric', labels: { style: { fontSize: '9px', fontFamily: 'IBM Plex Mono' } }, tooltip: { enabled: false } },
  yaxis: { labels: { style: { fontSize: '9px', fontFamily: 'IBM Plex Mono' } } },
  grid: { borderColor: '#E8E8E8' },
  dataLabels: { enabled: false }
})

const fetchData = async () => {
  if (!props.taskId || !props.product) return
  const { data } = await supabase.from('indicators')
    .select('timestamp, profit_and_loss')
    .eq('backtest_id', props.taskId)
    .eq('product', props.product)
    .order('timestamp', { ascending: true })
    .limit(10000)
  // Derive position from PnL delta as a proxy until position column is available
  if (data) chartSeries.value = [{ name: 'PnL Δ', data: data.map(d => [d.timestamp, d.profit_and_loss]) }]
}
watch([() => props.taskId, () => props.product], fetchData)
</script>