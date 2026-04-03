<template>
  <div ref="el" style="height: 100%; width: 100%;" />
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps(['taskId', 'product', 'day'])
const emit = defineEmits(['hover'])
const supabase = useSupabaseClient()
const { subscribe, broadcast, subscribeHover, broadcastHover } = useChartSync()
const { fetchAll } = useFetchAll()

const el = ref(null)
let lc          = null
let chart       = null
let ser         = null
let storedData  = []

const fetchData = async () => {
  if (!lc || !chart || !props.taskId || !props.product || !props.day) return
  
  let query = supabase.from('prices')
    .select('timestamp, profit_and_loss, day')
    .eq('backtest_id', props.taskId)
    .eq('product', props.product)

  if (props.day !== 'all' && props.day !== '') {
    query = query.eq('day', props.day)
  }

  const rawData = await fetchAll(() => query.order('timestamp', { ascending: true }))
  if (!rawData?.length) return

  let chartPoints = []
  
  if (props.day === 'all') {
    const minDay = Math.min(...rawData.map(d => d.day))
    const firstDayPoints = rawData.filter(d => d.day === minDay)
    const offset = firstDayPoints.length > 0 ? firstDayPoints[firstDayPoints.length - 1].profit_and_loss : 0

    chartPoints = rawData.map(d => ({
      time: d.timestamp,
      value: d.day > minDay ? (d.profit_and_loss + offset) : d.profit_and_loss,
      day: d.day 
    }))
  } else {
    chartPoints = rawData.map(d => ({ 
      time: d.timestamp, 
      value: d.profit_and_loss ?? 0,
      day: d.day 
    }))
  }

  if (ser) { try { chart.removeSeries(ser) } catch {} }
  
  const lastVal = chartPoints[chartPoints.length - 1].value
  const isProfit = lastVal >= 0
  
  const theme = isProfit 
    ? { line: '#00c800', top: 'rgba(0, 200, 0, 0.2)', bottom: 'rgba(0, 200, 0, 0)' } 
    : { line: '#ff4444', top: 'rgba(255, 68, 68, 0.2)', bottom: 'rgba(255, 68, 68, 0)' } 
  
  ser = chart.addSeries(lc.AreaSeries, {
    lineColor: theme.line, 
    lineWidth: 1.5,
    topColor: theme.top,
    bottomColor: theme.bottom,
    lastValueVisible: false,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  })

  storedData = chartPoints
  ser.setData(chartPoints)
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
    handleScale: { mouseWheel: true, axisPressedMouseMove: { time: true, price: true }, axisDoubleClickReset: true },
  })

  const syncFn = range => chart?.timeScale().setVisibleLogicalRange(range)
  subscribe(syncFn)
  chart.timeScale().subscribeVisibleLogicalRangeChange(range => broadcast(syncFn, range))

  const lookup = time => {
    if (time == null) { emit('hover', null); return }
    const pt = storedData.find(p => p.time === time)
    emit('hover', pt?.value ?? null)
  }
  subscribeHover(lookup)
  chart.subscribeCrosshairMove(param => {
    lookup(param.time ?? null)
    broadcastHover(lookup, param.time ?? null)
  })

  if (props.taskId && props.product && props.day) await fetchData()
})

onUnmounted(() => { chart?.remove(); chart = null; lc = null })
</script>
