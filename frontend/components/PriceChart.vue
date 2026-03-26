<template>
  <div style="height: 100%; width: 100%;">
    <client-only>
      <apexchart type="line" height="100%" :options="chartOptions" :series="chartSeries" />
    </client-only>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
const props = defineProps(['taskId', 'product', 'indicators', 'normalize', 'activeCategories'])
const supabase = useSupabaseClient()

const chartSeries = ref([])
const chartOptions = ref({
  chart: { 
    id: 'sync-price', 
    group: 'backtest-sync', 
    animations: { enabled: false },
    toolbar: { show: true, tools: { pan: true, zoom: true, download: false } }
  },
  colors: ['#FF0000', '#0000FF', '#000000', '#AA00FF', '#00BFA5'], // Ask, Bid, Mid, Wall1, Wall2
  stroke: { width: [1, 1, 1, 1.5, 1.5], curve: 'stepline' },
  xaxis: { type: 'numeric', labels: { style: { fontSize: '9px', fontFamily: 'IBM Plex Mono' } }, tooltip: { enabled: false } },
  yaxis: { labels: { style: { fontSize: '9px', fontFamily: 'IBM Plex Mono' } } },
  grid: { borderColor: '#E8E8E8' },
  legend: { show: false },
  annotations: { points: [], yaxis: [] },
  tooltip: { theme: 'light', shared: true }
})

const CAT_MAP = {
  'M': { color: '#FF8C00', size: 4 },
  'S': { color: '#00FF00', size: 5 },
  'B': { color: '#FF8C00', size: 6 },
  'I': { color: '#FF0000', size: 6 },
  'F': { color: '#FFD700', size: 5 }
}

const fetchData = async () => {
  if (!props.taskId || !props.product) return

  const { data: indData } = await supabase.from('indicators').select('*')
    .eq('backtest_id', props.taskId)
    .eq('product', props.product)
    .order('timestamp', { ascending: true })
    .limit(10000)
  const { data: trdData } = await supabase.from('trades').select('*')
    .eq('backtest_id', props.taskId)
    .eq('symbol', props.product)
    .limit(5000)

  if (!indData) return

  // 1. Normalization
  let data = indData
  let refKey = null
  
  if (props.normalize !== 'None') {
    refKey = props.normalize.toLowerCase().replace('mid', 'mid_price')
    data = indData.map(d => {
      const refVal = d[refKey] || d.mid_price || 0
      return {
        ...d,
        ask_price_1: d.ask_price_1 - refVal,
        bid_price_1: d.bid_price_1 - refVal,
        mid_price: d.mid_price - refVal,
        wallmid1: d.wallmid1 ? d.wallmid1 - refVal : null,
        wallmid2: d.wallmid2 ? d.wallmid2 - refVal : null,
        _refVal: refVal // Save for trade normalization
      }
    })
    chartOptions.value = { ...chartOptions.value, annotations: { ...chartOptions.value.annotations, yaxis: [{ y: 0, borderColor: '#000', strokeDashArray: 4 }] } }
  } else {
    chartOptions.value = { ...chartOptions.value, annotations: { ...chartOptions.value.annotations, yaxis: [] } }
  }

  // 2. Build Series Lines
  const s = [
    { name: 'Ask', data: data.map(d => [d.timestamp, d.ask_price_1]) },
    { name: 'Bid', data: data.map(d => [d.timestamp, d.bid_price_1]) }
  ]
  if (props.indicators.includes('Mid')) s.push({ name: 'Mid', data: data.map(d => [d.timestamp, d.mid_price]) })
  if (props.indicators.includes('WallMid1')) s.push({ name: 'Wall1', data: data.map(d => [d.timestamp, d.wallmid1]) })
  if (props.indicators.includes('WallMid2')) s.push({ name: 'Wall2', data: data.map(d => [d.timestamp, d.wallmid2]) })
  
  chartSeries.value = s

  // 3. Build Trade Markers
  if (trdData) {
    const points = []
    trdData.forEach(t => {
      const isOwn = t.buyer === 'SUBMISSION' || t.seller === 'SUBMISSION'
      const cat = isOwn ? 'F' : 'M' // Basic fallback, upgrade with your backend classifier if needed
      
      if (!props.activeCategories.includes(cat)) return

      // Normalize trade price
      let plotPrice = t.price
      if (props.normalize !== 'None') {
        const row = data.find(d => d.timestamp === t.timestamp)
        if (row) plotPrice = t.price - row._refVal
      }

      const style = CAT_MAP[cat]
      points.push({
        x: t.timestamp,
        y: plotPrice,
        marker: { size: style.size, fillColor: style.color, strokeColor: '#000' },
        label: { text: `${t.quantity}`, style: { fontSize: '9px', background: 'transparent' } }
      })
    })
    chartOptions.value = { ...chartOptions.value, annotations: { ...chartOptions.value.annotations, points } }
  }
}

watch([() => props.taskId, () => props.product, () => props.indicators, () => props.normalize, () => props.activeCategories], fetchData, { deep: true })
</script>