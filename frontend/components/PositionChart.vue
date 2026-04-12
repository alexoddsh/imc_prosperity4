<template>
  <div ref="el" style="height: 100%; width: 100%;" />
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps(['taskId', 'product', 'day', 'priceData', 'tradeData'])
const emit = defineEmits(['hover'])
const { subscribe, broadcast, subscribeHover, broadcastHover } = useChartSync()

const el = ref(null)
let lc         = null
let chart      = null
let ser        = null
let storedData = []

const render = () => {
  if (!lc || !chart) return
  const priceRows = props.priceData
  const tradeRows = props.tradeData ?? []
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

  storedData = chartData
  ser.setData(chartData)
  chart.timeScale().fitContent()
}

watch([() => props.priceData, () => props.tradeData], render)

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

  render()
})

onUnmounted(() => { chart?.remove(); chart = null; lc = null })
</script>
