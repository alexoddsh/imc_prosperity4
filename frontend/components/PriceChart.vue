<template>
  <div ref="el" style="height: 100%; width: 100%; position: relative;" @contextmenu.prevent>
    <div ref="tooltipEl" class="trade-tooltip" style="display:none;" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps(['taskId', 'product', 'day', 'indicators', 'normalize', 'activeCategories', 'qtyRange', 'obLevels', 'showAlgoOb'])
const emit = defineEmits(['obSnapshot'])
const supabase = useSupabaseClient()
const { subscribe, broadcast, broadcastHover } = useChartSync()
const { fetchAll } = useFetchAll()

const el         = ref(null)
const tooltipEl  = ref(null)
let lc           = null
let chart        = null
let series       = {}
let primitive    = null
let dayLinePrim  = null
let algoObPrim   = null
let rawTrades      = []
let rawAlgoOb      = []
let cachedPriceRaw    = null
let cachedTradeData   = null
let cachedInternalData = null

const SHORT = { MAKER1: 'M1', TAKER1: 'T1', MAKER2: 'M2', TAKER2: 'T2', INFORMED1: 'I1', TOXIC: 'TX', ALGO: 'AL' }
const FG    = { MAKER1: '#fff', TAKER1: '#000', MAKER2: '#fff', TAKER2: '#000', INFORMED1: '#fff', TOXIC: '#fff', ALGO: '#000' }

function badgeHtml(cls) {
  const cfg = CAT_CFG[cls]
  const fg  = FG[cls] ?? '#fff'
  return `<span style="display:inline-block;background:${cfg.color};color:${fg};padding:1px 4px;font-size:9px;font-weight:700;letter-spacing:0.3px;">${SHORT[cls] ?? cls}</span>`
}

function showTooltip(pt, x, y) {
  if (!tooltipEl.value) return
  const { buyer_cls, seller_cls, qty, price } = pt
  tooltipEl.value.innerHTML =
    `S:${badgeHtml(seller_cls)} ${qty}@${price} B:${badgeHtml(buyer_cls)}`
  tooltipEl.value.style.display = 'block'
  const rect = el.value.getBoundingClientRect()
  const tw = tooltipEl.value.offsetWidth
  let left = x + 10
  if (left + tw > rect.width - 4) left = x - tw - 10
  tooltipEl.value.style.left = left + 'px'
  tooltipEl.value.style.top  = Math.max(2, y - 18) + 'px'
}

function hideTooltip() {
  if (tooltipEl.value) tooltipEl.value.style.display = 'none'
}

function showAlgoObTooltip(pt, x, y) {
  if (!tooltipEl.value) return
  const dir = pt.qty > 0 ? 'LONG' : 'SHORT'
  const color = pt.qty > 0 ? '#7c3e0e' : '#000000'
  tooltipEl.value.innerHTML =
    `<span style="color:${color};font-weight:700">${dir}</span> ${Math.abs(pt.qty)}@${pt.price}`
  tooltipEl.value.style.display = 'block'
  const rect = el.value.getBoundingClientRect()
  const tw = tooltipEl.value.offsetWidth
  let left = x + 10
  if (left + tw > rect.width - 4) left = x - tw - 10
  tooltipEl.value.style.left = left + 'px'
  tooltipEl.value.style.top  = Math.max(2, y - 18) + 'px'
}

// ── Marker style config ──────────────────────────────────────────────────────
const CAT_CFG = {
  MAKER1:    { color: '#FF8C00', stroke: '#000', r: 11 },
  MAKER2:    { color: '#b50000', stroke: '#000', r: 11 },
  TAKER1:    { color: '#00CC00', stroke: '#000', r: 8  },
  TAKER2:    { color: '#00a500', stroke: '#000', r: 8  },
  INFORMED1: { color: '#6A3FE5', stroke: '#000', r: 8  },
  TOXIC:     { color: '#CC00CC', stroke: '#000', r: 8  },
  ALGO:      { color: '#FFD700', stroke: '#BB9000', r: 9 },
}
// Draw order: MAKER1 first = rendered behind everything else
const DRAW_ORDER = ['MAKER1', 'TAKER1', 'MAKER2', 'TAKER2', 'INFORMED1', 'TOXIC', 'ALGO']

function drawShape(ctx, cls, x, y, pr) {
  const cfg = CAT_CFG[cls]
  if (!cfg) return
  const r = cfg.r * pr
  ctx.save()

  if (cls === 'MAKER1' || cls === 'MAKER2') {
    // Large square — drawn first, behind all others
    ctx.fillStyle   = cfg.color
    ctx.strokeStyle = cfg.stroke
    ctx.lineWidth   = 1.2 * pr
    ctx.fillRect(x - r, y - r, r * 2, r * 2)
    ctx.strokeRect(x - r, y - r, r * 2, r * 2)

  } else if (cls === 'TAKER1' || cls === 'TAKER2') {
    // Filled triangle pointing up
    ctx.fillStyle   = cfg.color
    ctx.strokeStyle = cfg.stroke
    ctx.lineWidth   = 1 * pr
    ctx.beginPath()
    ctx.moveTo(x,         y - r)
    ctx.lineTo(x + r,     y + r * 0.75)
    ctx.lineTo(x - r,     y + r * 0.75)
    ctx.closePath()
    ctx.fill()
    ctx.stroke()

  } else if (cls === 'INFORMED1' || cls === 'TOXIC') {
    // 5-pointed star
    const inner = r * 0.42
    ctx.fillStyle   = cfg.color
    ctx.strokeStyle = cfg.stroke
    ctx.lineWidth   = 0.8 * pr
    ctx.beginPath()
    for (let i = 0; i < 10; i++) {
      const angle = (i * Math.PI / 5) - Math.PI / 2
      const rad   = i % 2 === 0 ? r : inner
      const px    = x + rad * Math.cos(angle)
      const py    = y + rad * Math.sin(angle)
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)
    }
    ctx.closePath()
    ctx.fill()
    ctx.stroke()

  } else if (cls === 'ALGO') {
    // Bold X cross
    ctx.strokeStyle = cfg.stroke
    ctx.lineWidth   = 3.5 * pr
    ctx.lineCap     = 'round'
    ctx.beginPath()
    ctx.moveTo(x - r, y - r)
    ctx.lineTo(x + r, y + r)
    ctx.moveTo(x + r, y - r)
    ctx.lineTo(x - r, y + r)
    ctx.stroke()
    // Thinner gold inner line
    ctx.strokeStyle = cfg.color
    ctx.lineWidth   = 2 * pr
    ctx.beginPath()
    ctx.moveTo(x - r, y - r)
    ctx.lineTo(x + r, y + r)
    ctx.moveTo(x + r, y - r)
    ctx.lineTo(x - r, y + r)
    ctx.stroke()
  }

  ctx.restore()
}

// ── Custom series primitive ───────────────────────────────────────────────────
function makePrimitive() {
  let _series   = null
  let _chart    = null
  let _request  = null
  let _trades   = []
  let _active   = new Set()
  let _qtyRange = [0, Infinity]
  let _pts      = []   // pre-computed [{x,y,cls,buyer_cls,seller_cls,qty,price}]

  const _view = {
    renderer() {
      return {
        draw(target) {
          if (!_pts.length) return
          target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
            // MAKER1 drawn first (behind), ALGO last (on top)
            const sorted = [..._pts].sort(
              (a, b) => DRAW_ORDER.indexOf(a.cls) - DRAW_ORDER.indexOf(b.cls)
            )
            for (const { x, y, cls } of sorted) {
              drawShape(ctx, cls, Math.round(x * hr), Math.round(y * vr), hr)
            }
          })
        }
      }
    },
    zOrder() { return 'top' }
  }

  return {
    attached({ series, chart, requestUpdate }) {
      _series  = series
      _chart   = chart
      _request = requestUpdate
    },
    detached() { _series = null; _chart = null; _request = null },
    paneViews() { return [_view] },
    updateAllViews() {
      _pts = []
      if (!_series || !_chart) return
      const ts = _chart.timeScale()
      const [qMin, qMax] = _qtyRange
      for (const t of _trades) {
        if (!_active.has(t.cls)) continue
        if (t.qty < qMin || t.qty > qMax) continue
        const x = ts.timeToCoordinate(t.time)
        const y = _series.priceToCoordinate(t.price)
        if (x == null || y == null) continue
        _pts.push({ x, y, cls: t.cls, buyer_cls: t.buyer_cls, seller_cls: t.seller_cls, qty: t.qty, price: t.price })
      }
    },
    setData(trades, active, qtyRange) {
      _trades   = trades
      _active   = new Set(active)
      _qtyRange = qtyRange ?? [0, Infinity]
      _request?.()
    },
    findNearest(x, y, threshold = 14) {
      let best = null, bestD = threshold
      for (const pt of _pts) {
        const d = Math.hypot(pt.x - x, pt.y - y)
        if (d < bestD) { bestD = d; best = pt }
      }
      return best
    },
  }
}

function makeAlgoObPrimitive() {
  let _series  = null
  let _chart   = null
  let _request = null
  let _orders  = []
  let _pts     = []

  const _view = {
    renderer() {
      return {
        draw(target) {
          if (!_pts.length) return
          target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
            for (const { x, y, qty } of _pts) {
              const cx = Math.round(x * hr)
              const cy = Math.round(y * vr)
              const r  = 7 * hr
              const inner = r * 0.42
              ctx.save()
              ctx.fillStyle = qty > 0 ? '#7c3e0e' : '#000000'
              ctx.beginPath()
              for (let i = 0; i < 10; i++) {
                const angle = (i * Math.PI / 5) - Math.PI / 2
                const rad   = i % 2 === 0 ? r : inner
                const px    = cx + rad * Math.cos(angle)
                const py    = cy + rad * Math.sin(angle)
                i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)
              }
              ctx.closePath()
              ctx.fill()
              ctx.restore()
            }
          })
        }
      }
    },
    zOrder() { return 'normal' }
  }

  return {
    attached({ series, chart, requestUpdate }) { _series = series; _chart = chart; _request = requestUpdate },
    detached() { _series = null; _chart = null; _request = null },
    paneViews() { return [_view] },
    updateAllViews() {
      _pts = []
      if (!_series || !_chart) return
      const ts = _chart.timeScale()
      for (const o of _orders) {
        const x = ts.timeToCoordinate(o.time)
        const y = _series.priceToCoordinate(o.price)
        if (x == null || y == null) continue
        _pts.push({ x, y, qty: o.qty, price: o.price })
      }
    },
    setData(orders) {
      _orders = orders
      _request?.()
    },
    findNearest(x, y, threshold = 14) {
      let best = null, bestD = threshold
      for (const pt of _pts) {
        const d = Math.hypot(pt.x - x, pt.y - y)
        if (d < bestD) { bestD = d; best = pt }
      }
      return best
    },
  }
}

function makeDayLinePrimitive() {
  let _chart = null
  const _view = {
    renderer() {
      return {
        draw(target) {
          if (!_chart) return
          target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio: hr, bitmapSize }) => {
            const x = _chart.timeScale().timeToCoordinate(1000000)
            if (x == null) return
            ctx.save()
            ctx.strokeStyle = '#aaaaaa'
            ctx.lineWidth = 1.5 * hr
            ctx.setLineDash([5 * hr, 4 * hr])
            ctx.beginPath()
            ctx.moveTo(Math.round(x * hr) + 0.5, 0)
            ctx.lineTo(Math.round(x * hr) + 0.5, bitmapSize.height)
            ctx.stroke()
            ctx.restore()
          })
        }
      }
    },
    zOrder() { return 'normal' }
  }
  return {
    attached({ chart }) { _chart = chart },
    detached() { _chart = null },
    paneViews() { return [_view] },
  }
}

const valid = v => v != null && v !== 0

const clearSeries = () => {
  if (primitive && series.Ask) {
    try { series.Ask.detachPrimitive(primitive) } catch (e) {}
  }
  if (dayLinePrim && series.Ask) {
    try { series.Ask.detachPrimitive(dayLinePrim) } catch (e) {}
  }
  if (algoObPrim && series.Ask) {
    try { series.Ask.detachPrimitive(algoObPrim) } catch (e) {}
  }

  Object.keys(series).forEach(key => {
    try { chart.removeSeries(series[key]) } catch (e) {}
  })

  series      = {}
  primitive   = null
  dayLinePrim = null
  algoObPrim  = null
  rawTrades   = []
  rawAlgoOb   = []
}

const pushMarkers = () => {
  primitive?.setData(rawTrades, props.activeCategories ?? [], props.qtyRange ?? [0, Infinity])
}

const pushAlgoOb = () => {
  if (!series.Ask) return
  if (props.showAlgoOb) {
    if (!algoObPrim) {
      algoObPrim = makeAlgoObPrimitive()
      series.Ask.attachPrimitive(algoObPrim)
    }
    const algoTradeTimes = new Set(rawTrades.filter(t => t.cls === 'ALGO').map(t => Number(t.time)))
    algoObPrim.setData(rawAlgoOb.filter(o => o.qty !== 0 && !algoTradeTimes.has(Number(o.time))))
  } else if (algoObPrim) {
    try { series.Ask.detachPrimitive(algoObPrim) } catch (e) {}
    algoObPrim = null
  }
}

const renderChart = (priceRaw, tradeData, internalData) => {
  if (!lc || !chart || !priceRaw) return

  clearSeries()

  let prc = priceRaw
  if (props.normalize !== 'None') {
    const NORM_KEY = { Mid: 'mid_price', WallMid1: 'wallmid1', WallMid2: 'wallmid2', 'WallMid2 (SMA)': 'wallmidsma', WallMid3: 'wallmid3', WallmidO: 'wallmido'   }
    const refKey = NORM_KEY[props.normalize]
    prc = priceRaw.map(d => {
      const ref = d[refKey]
      if (ref == null) return null
      return {
        ...d,
        ask_price_1: d.ask_price_1 - ref,
        ask_price_2: d.ask_price_2 != null ? d.ask_price_2 - ref : null,
        ask_price_3: d.ask_price_3 != null ? d.ask_price_3 - ref : null,
        bid_price_1: d.bid_price_1 - ref,
        bid_price_2: d.bid_price_2 != null ? d.bid_price_2 - ref : null,
        bid_price_3: d.bid_price_3 != null ? d.bid_price_3 - ref : null,
        mid_price: d.mid_price   - ref,
        wallmid1: d.wallmid1 != null ? d.wallmid1 - ref : null,
        wallmid2: d.wallmid2 != null ? d.wallmid2 - ref : null,
        wallmidsma: d.wallmidsma != null ? d.wallmid2 - ref : null,
        wallmid3: d.wallmid3 != null ? d.wallmid3 - ref: null,
        wallmido: d.wallmido != null ? d.wallmido - ref: null,
        _ref: ref,
      }
    }).filter(Boolean)
  }

  const lineOpts = {
    lineWidth: 1,
    lineType: 1,
    lastValueVisible: false,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  }

  const levels = props.obLevels ?? [1]
  const OB_COLORS = {
    ask: { 1: '#FF0000', 2: '#FF8888', 3: '#FFBBBB' },
    bid: { 1: '#0000FF', 2: '#8888FF', 3: '#BBBBFF' },
  }

  for (const lvl of [1, 2, 3]) {
    if (!levels.includes(lvl)) continue
    const askKey = `ask_price_${lvl}`
    const bidKey = `bid_price_${lvl}`
    const askS = chart.addSeries(lc.LineSeries, { ...lineOpts, color: OB_COLORS.ask[lvl] })
    const bidS = chart.addSeries(lc.LineSeries, { ...lineOpts, color: OB_COLORS.bid[lvl] })
    askS.setData(prc.filter(d => valid(d[askKey])).map(d => ({ time: d.timestamp, value: d[askKey] })))
    bidS.setData(prc.filter(d => valid(d[bidKey])).map(d => ({ time: d.timestamp, value: d[bidKey] })))
    series[`Ask${lvl}`] = askS
    series[`Bid${lvl}`] = bidS
  }

  series.Ask = series.Ask1 ?? series.Ask2 ?? series.Ask3

  if (props.indicators.includes('Mid')) {
    series.Mid = chart.addSeries(lc.LineSeries, { ...lineOpts, color: '#000000' })
    series.Mid.setData(prc.filter(d => valid(d.mid_price)).map(d => ({ time: d.timestamp, value: d.mid_price })))
  }
  if (props.indicators.includes('WallMid1')) {
    series.Wall1 = chart.addSeries(lc.LineSeries, { ...lineOpts, color: '#AA00FF', lineWidth: 1.5 })
    series.Wall1.setData(prc.filter(d => valid(d.wallmid1)).map(d => ({ time: d.timestamp, value: d.wallmid1 })))
  }
  if (props.indicators.includes('WallMid2')) {
    series.Wall2 = chart.addSeries(lc.LineSeries, { ...lineOpts, color: '#00BFA5', lineWidth: 1.5 })
    series.Wall2.setData(prc.filter(d => valid(d.wallmid2)).map(d => ({ time: d.timestamp, value: d.wallmid2 })))
  }
  if (props.indicators.includes('WallMid2 (SMA)')) {
    series.Wall2SMA = chart.addSeries(lc.LineSeries, { ...lineOpts, color: '#ff4297', lineWidth: 1.5 })
    series.Wall2SMA.setData(prc.filter(d => valid(d.wallmidsma)).map(d => ({ time: d.timestamp, value: d.wallmidsma })))
  }
  if (props.indicators.includes('WallMid3')) {
    series.Wall3 = chart.addSeries(lc.LineSeries, { ...lineOpts, color: '#50ca54', lineWidth: 1.5 })
    series.Wall3.setData(prc.filter(d => valid(d.wallmid3)).map(d => ({ time: d.timestamp, value: d.wallmid3 })))
  }
  if (props.indicators.includes('WallMidO')) {
    series.WallO = chart.addSeries(lc.LineSeries, { ...lineOpts, color: '#b91d92', lineWidth: 1.5 })
    series.WallO  .setData(prc.filter(d => valid(d.wallmido)).map(d => ({ time: d.timestamp, value: d.wallmido })))
  }

  if (props.normalize !== 'None' && series.Ask) {
    series.Ask.createPriceLine({ price: 0, color: '#999', lineWidth: 1, lineStyle: 2, axisLabelVisible: false })
  }

  primitive = makePrimitive()
  if (series.Ask) {
    series.Ask.attachPrimitive(primitive)
    dayLinePrim = makeDayLinePrimitive()
    series.Ask.attachPrimitive(dayLinePrim)
  }

  if (tradeData) {
    tradeData.forEach(t => {
      let ref = 0
      if (props.normalize !== 'None') {
        const match = prc.find(p => p.timestamp === t.timestamp)
        if (match) ref = match._ref
      }
      const price = t.price - ref
      ;[t.buyer_class, t.seller_class].forEach(cls => {
        if (CAT_CFG[cls]) rawTrades.push({ time: t.timestamp, price, cls, qty: t.quantity, buyer_cls: t.buyer_class, seller_cls: t.seller_class })
      })
    })
    pushMarkers()
  }

  if (internalData) {
    internalData.forEach(o => {
      let ref = 0
      if (props.normalize !== 'None') {
        const match = prc.find(p => p.timestamp === o.timestamp)
        if (match) ref = match._ref
      }
      rawAlgoOb.push({ time: o.timestamp, price: o.order_price - ref, qty: o.order_quantity })
    })
    pushAlgoOb()
  }

  chart.timeScale().fitContent()
}

const fetchData = async () => {
  if (!lc || !chart || !props.taskId || !props.product || props.day === '') return

  let priceQuery = supabase.from('prices')
    .select('*')
    .eq('backtest_id', props.taskId)
    .eq('product', props.product)

  let tradeQuery = supabase.from('trades')
    .select('*')
    .eq('backtest_id', props.taskId)
    .eq('symbol', props.product)

  let internalQuery = supabase.from('internal')
    .select('*')
    .eq('backtest_id', props.taskId)
    .eq('product', props.product)
    .neq('order_quantity', 0)

  if (props.day !== 'all') {
    priceQuery    = priceQuery.eq('day', props.day)
    tradeQuery    = tradeQuery.eq('day', props.day)
    internalQuery = internalQuery.eq('day', props.day)
  }

  priceQuery    = priceQuery.order('timestamp', { ascending: true })
  tradeQuery    = tradeQuery.order('timestamp', { ascending: true })
  internalQuery = internalQuery.order('timestamp', { ascending: true })

  const [priceRaw, tradeData, internalData] = await Promise.all([
    fetchAll(() => priceQuery),
    fetchAll(() => tradeQuery),
    fetchAll(() => internalQuery),
  ])

  cachedPriceRaw     = priceRaw
  cachedTradeData    = tradeData
  cachedInternalData = internalData

  renderChart(priceRaw, tradeData, internalData)
}

watch([() => props.taskId, () => props.product, () => props.day], fetchData)
watch([() => props.indicators, () => props.normalize, () => props.obLevels], () => renderChart(cachedPriceRaw, cachedTradeData, cachedInternalData), { deep: true })
watch([() => props.activeCategories, () => props.qtyRange], pushMarkers, { deep: true })
watch(() => props.showAlgoOb, pushAlgoOb)

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
    rightPriceScale: { borderColor: '#ddd', scaleMargins: { top: 0.05, bottom: 0.05 } },
    timeScale: {
      borderColor: '#ddd',
      uniformDistribution: true,
      minBarSpacing: 0,
      tickMarkFormatter: t => String(t),
    },
    localization: { timeFormatter: t => `t=${t}` },
    handleScroll: { mouseWheel: false, pressedMouseMove: true },
    handleScale: {
      mouseWheel: true,
      axisPressedMouseMove: { time: true, price: true },
      axisDoubleClickReset: true,
    },
  })

  // Right-drag → axis-locked zoom (horizontal or vertical, locked after 6px)
  let rDrag = null
  el.value.addEventListener('mousedown', e => {
    if (e.button !== 2) return
    const range = chart.timeScale().getVisibleLogicalRange()
    if (!range) return
    const ps = chart.priceScale('right').getVisibleRange() ?? null
    rDrag = { x: e.clientX, y: e.clientY, from: range.from, to: range.to, ps, dir: null }
  })
  el.value.addEventListener('mousemove', e => {
    if (rDrag) {
      const dx = e.clientX - rDrag.x
      const dy = e.clientY - rDrag.y

      // Lock direction after 6px of movement to prevent axis bleed
      if (!rDrag.dir && (Math.abs(dx) > 6 || Math.abs(dy) > 6)) {
        rDrag.dir = Math.abs(dx) >= Math.abs(dy) ? 'h' : 'v'
        el.value.style.cursor = rDrag.dir === 'h' ? 'ew-resize' : 'ns-resize'
      }

      if (rDrag.dir === 'h') {
        const mid  = (rDrag.from + rDrag.to) / 2
        const half = ((rDrag.to - rDrag.from) / 2) * Math.exp(-dx * 0.005)
        chart.timeScale().setVisibleLogicalRange({ from: mid - half, to: mid + half })
      } else if (rDrag.dir === 'v' && rDrag.ps) {
        const { from, to } = rDrag.ps
        const mid  = (from + to) / 2
        const half = ((to - from) / 2) * Math.exp(dy * 0.005)
        chart.priceScale('right').setVisibleRange({ from: mid - half, to: mid + half })
      }
      return
    }
    const rect = el.value.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const algoPt = algoObPrim?.findNearest(x, y)
    if (algoPt) { showAlgoObTooltip(algoPt, x, y); return }
    if (!primitive) { hideTooltip(); return }
    const pt = primitive.findNearest(x, y)
    if (pt) showTooltip(pt, x, y)
    else    hideTooltip()
  })
  el.value.addEventListener('mouseup', e => { if (e.button === 2) { rDrag = null; el.value.style.cursor = '' } })
  el.value.addEventListener('mouseleave', () => { rDrag = null; if (el.value) el.value.style.cursor = ''; hideTooltip() })

  const syncFn = range => chart?.timeScale().setVisibleLogicalRange(range)
  subscribe(syncFn)
  chart.timeScale().subscribeVisibleLogicalRangeChange(range => broadcast(syncFn, range))
  chart.subscribeCrosshairMove(param => {
    broadcastHover(null, param.time ?? null)
    if (param.time != null && cachedPriceRaw?.length) {
      const row = cachedPriceRaw.find(r => r.timestamp === param.time)
      if (row) emit('obSnapshot', row)
    }
  })

  if (props.taskId && props.product) await fetchData()
})

onUnmounted(() => { chart?.remove(); chart = null; lc = null })
</script>
