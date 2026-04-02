<template>
  <div ref="el" style="height: 100%; width: 100%;" />
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps(['taskId', 'product', 'day'])
const supabase = useSupabaseClient()
const { subscribe, broadcast } = useChartSync()
const { fetchAll } = useFetchAll()

const el = ref(null)
let lc    = null
let chart = null
let ser   = null

const fetchData = async () => {
  if (!lc || !chart || !props.taskId || !props.product || !props.day) return

  let priceQ = supabase.from('prices')
    .select('timestamp, day') 
    .eq('backtest_id', props.taskId)
    .eq('product', props.product)
    .order('timestamp', { ascending: true })

  let tradeQ = supabase.from('trades')
    .select('timestamp, algo_position, day')
    .eq('backtest_id', props.taskId)
    .eq('symbol', props.product)
    .order('timestamp', { ascending: true })

  if (props.day !== 'all' && props.day !== '') {
    priceQ = priceQ.eq('day', props.day)
    tradeQ = tradeQ.eq('day', props.day)
  }

  const [priceRows, tradeRows] = await Promise.all([
    fetchAll(() => priceQ),
    fetchAll(() => tradeQ),
  ])

  if (!priceRows?.length) return

  const minDay = Math.min(...priceRows.map(p => p.day))
  
  let dayOffset = 0
  if (props.day === 'all') {
    const firstDayTrades = tradeRows.filter(t => t.day === minDay)
    if (firstDayTrades.length > 0) {
      dayOffset = firstDayTrades[firstDayTrades.length - 1].algo_position
    }
  }

  let tradeIdx = 0
  let lastPos = 0
  
  const chartData = priceRows.map(p => {
    while (tradeIdx < tradeRows.length && tradeRows[tradeIdx].timestamp <= p.timestamp) {
      lastPos = tradeRows[tradeIdx].algo_position
      tradeIdx++
    }
    
    const isPastFirstDay = props.day === 'all' && p.day > minDay
    const finalValue = isPastFirstDay ? (lastPos + dayOffset) : lastPos

    return { time: p.timestamp, value: finalValue }
  })

  if (ser) { try { chart.removeSeries(ser) } catch {} }
  ser = chart.addSeries(lc.BaselineSeries, {
    baseValue: { type: 'price', price: 0 },
    topLineColor: '#00c800', 
    topFillColor1: 'rgba(0, 200, 0, 0.12)',
    bottomLineColor: '#ff4444', 
    bottomFillColor1: 'rgba(255, 68, 68, 0.12)',
    lineWidth: 1.5,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  })

  ser.setData(chartData)
  chart.timeScale().fitContent()
}

watch([() => props.taskId, () => props.product, () => props.day], fetchData)

onMounted(async () => {
  lc = await import('lightweight-charts')
  chart = lc.createChart(el.value, {
    autoSize: true,
    layout: {
      background: { type: lc.ColorType.Solid, color: '#ffffff' },
      textColor: '#555',
      fontFamily: 'IBM Plex Mono',
      fontSize: 9,
    },
    grid: { vertLines: { color: '#f0f0f0' }, horzLines: { color: '#f0f0f0' } },
    crosshair: { mode: lc.CrosshairMode.Normal },
    rightPriceScale: { borderColor: '#ddd', scaleMargins: { top: 0.1, bottom: 0.05 } },
    timeScale: { borderColor: '#ddd', uniformDistribution: true, minBarSpacing: 0, tickMarkFormatter: t => String(t) },
    localization: { timeFormatter: t => `t=${t}` },
    handleScroll: { mouseWheel: false, pressedMouseMove: true },
    handleScale: { mouseWheel: false, axisPressedMouseMove: { time: true, price: true }, axisDoubleClickReset: true },
  })

  const syncFn = range => chart?.timeScale().setVisibleLogicalRange(range)
  subscribe(syncFn)
  chart.timeScale().subscribeVisibleLogicalRangeChange(range => broadcast(syncFn, range))

  if (props.taskId && props.product) await fetchData()
})

onUnmounted(() => { chart?.remove(); chart = null; lc = null })
</script>
