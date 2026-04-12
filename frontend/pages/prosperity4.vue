<template>
  <div class="app-wrapper">
    <main class="chart-area">
      <div class="main-chart">
        <PriceChart
          :taskId="activeTaskId"
          :product="selectedProduct"
          :day="selectedDay"
          :indicators="selectedInd"
          :normalize="normBy"
          :activeCategories="activeCategories"
          :qtyRange="qtyRange"
          :obLevels="obLevels"
          :showAlgoOb="showAlgoOb"
          :priceData="priceData"
          :tradeData="tradeData"
          :internalData="internalData"
          @obSnapshot="r => obSnap = r"
        />
      </div>
      <div class="sub-chart">
        <PnLChart
        :taskId="activeTaskId"
        :product="selectedProduct"
        :day="selectedDay"
        :priceData="priceData"
        @hover="v => hoverPnl = v"
        />
      </div>
      <div class="sub-chart">
        <PositionChart
        :taskId="activeTaskId"
        :product="selectedProduct"
        :day="selectedDay"
        :priceData="priceData"
        :tradeData="tradeData"
        @hover="v => hoverPos = v"
        />
      </div>
    </main>

    <aside class="control-sidebar">
      <div class="info-box">
        <b>{{ selectedProduct || '—' }}</b> | {{ timeRange }}<br>
        trades: {{ stats.trades }} (own: {{ stats.own }})<br>
        PnL: <b>{{ stats.pnl.toFixed(0) }}</b><br>Cum. PnL: <b>{{ hoverPnl !== null ? hoverPnl.toFixed(0) : '—' }}</b> Pos: <b>{{ hoverPos !== null ? hoverPos.toFixed(0) : '—' }}</b>
      </div>

      <div>
        <span class="sl">run history</span>
        <select v-model="activeTaskId" class="raw-select mono-select" style="margin-bottom:4px;">
          <option value="" disabled>— select run —</option>
          <option v-for="r in formattedRuns" :key="r.id" :value="r.id">
            {{ r.label }}
          </option>
        </select>
      </div>

      <div>
        <span class="sl">product</span>
        <select v-model="selectedProduct" class="raw-select" :disabled="!availableProducts.length">
          <option value="" disabled>— select product —</option>
          <option v-for="p in availableProducts" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>

      <div>
        <span class="sl">day</span>
        <select v-model="selectedDay" class="raw-select" :disabled="!availableProducts.length">
          <option value="" disabled>— select day —</option>
          <option value="all">All</option>
          <option :value="-2">Day -2</option>
          <option :value="-1">Day -1</option>
        </select>
      </div>

      <div>
        <span class="sl">indicators</span>
        <div class="ind-dropdown">
          <div class="raw-select ind-trigger" @click="indOpen = !indOpen">
            {{ selectedInd.length ? selectedInd.join(', ') : '—' }}
          </div>
          <div v-if="indOpen" class="ind-options">
            <label v-for="opt in ['Mid', 'WallMid3', 'WallMidO']" :key="opt">
              <input type="checkbox" :value="opt" v-model="selectedInd"> {{ opt }}
            </label>
          </div>
        </div>
      </div>

      <div class="bx">
        <div>
          <span class="sl">order book</span>
          <div class="checkbox-list">
            <label v-for="lvl in [1, 2, 3]" :key="lvl">
              <input type="checkbox" :value="lvl" v-model="obLevels"> L{{ lvl }}
            </label>
          </div>
        </div>
        <div>
          <span class="sl">show algo orders</span>
          <button class="cat-grid button" @click="showAlgoOb=!showAlgoOb" 
              :style="{
              backgroundColor: showAlgoOb ? '#ffffff' : '#1b0606',
              color: '#de0404',
              opacity: showAlgoOb ? 1 : 0.4
            }">{{ showAlgoOb }}</button>
        </div>
      </div>

      <div>
        <span class="sl">normalize</span>
        <select v-model="normBy" class="raw-select">
          <option value="None">None</option>
          <option v-for="opt in ['Mid', 'WallMid1', 'WallMid2', 'WallMid2 (SMA)', 'WallMid3']" :key="opt">{{ opt }}</option>
        </select>
      </div>

      <div>
        <span class="sl">traders</span>
        <div class="cat-grid">
          <button v-for="cat in categories" :key="cat.name"
            :style="{
              backgroundColor: cat.active ? cat.bg : '#eee',
              color: cat.active ? cat.fg : '#999',
              opacity: cat.active ? 1 : 0.4
            }"
            @click="cat.active = !cat.active">
            {{ cat.name }}
          </button>
        </div>
      </div>

      <div>
        <span class="sl">qty filter</span>
        <div style="display:flex; gap:4px; align-items:center;">
          <input type="number" v-model.number="qtyRange[0]" min="0" class="raw-input" style="width:50%;" />
          <span style="font-size:10px; color:#999;">–</span>
          <input type="number" v-model.number="qtyRange[1]" min="0" class="raw-input" style="width:50%;" />
        </div>
      </div>

      <div style="margin-top: auto; display:flex; flex-direction:column; gap:6px;">
        <div>
          <span class="sl">orderbook</span>
          <div v-if="obRows" class="ob-widget">
            <div v-for="(row, i) in obRows.asks" :key="'a'+i" class="ob-row ob-ask">
              <span class="ob-v">{{ row.vol ?? '' }}</span>
              <div class="ob-bar-track"><div class="ob-bar ob-bar-ask" :style="{ width: row.pct + '%' }"></div></div>
              <span class="ob-p">{{ row.price }}</span>
            </div>
            <div class="ob-spread-line">{{ obRows.spread != null ? obRows.spread.toFixed(1) : '·' }}</div>
            <div v-for="(row, i) in obRows.bids" :key="'b'+i" class="ob-row ob-bid">
              <span class="ob-v">{{ row.vol ?? '' }}</span>
              <div class="ob-bar-track"><div class="ob-bar ob-bar-bid" :style="{ width: row.pct + '%' }"></div></div>
              <span class="ob-p">{{ row.price }}</span>
            </div>
          </div>
          <div v-else class="ob-empty">— hover chart —</div>
        </div>
        <div class="upload-container">
          <input type="file" accept=".log" @change="handleFileUpload"/>
        </div>
      </div>

      <div>
        <span class="sl">algo</span>
        <input v-model="algoName" class="raw-input" style="margin-bottom: 8px;" />
        <span class="sl">round</span>
        <input v-model="roundId" class="raw-input" style="margin-bottom: 8px;" />
        <button class="run-btn" @click="runBacktest" :disabled="isRunning">
          {{ isRunning ? 'RUNNING...' : 'RUN' }}
        </button>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
const config = useRuntimeConfig()
const route = useRoute()
const supabase = useSupabaseClient()
const { priceData, tradeData, internalData, load: loadBacktestData } = useBacktestData()

const activeTaskId = ref(route.query.taskId || '')
const isRunning = ref(false)
const algoName = ref('version.py')
const roundId = ref('0')
const recentRuns = ref([])
const availableProducts = ref([])
const selectedProduct = ref('')
const selectedDay = ref('')
const timeRange = ref('-')
const selectedInd = ref([])
const indOpen = ref(false)
const normBy = ref('None')
const obLevels = ref([1])
const showAlgoOb = ref(false)

const stats    = ref({ trades: 0, own: 0, pnl: 0 })
const hoverPnl = ref(null)
const hoverPos = ref(null)
const qtyRange = ref([1, 100])
const obSnap   = ref(null)

const obRows = computed(() => {
  const r = obSnap.value
  if (!r) return null
  const vols = [1,2,3].flatMap(i => [r[`ask_volume_${i}`] ?? 0, r[`bid_volume_${i}`] ?? 0])
  const maxVol = Math.max(...vols, 1)
  const asks = [3,2,1].map(i => ({
    price: r[`ask_price_${i}`],
    vol:   r[`ask_volume_${i}`] ?? null,
    pct:   ((r[`ask_volume_${i}`] ?? 0) / maxVol) * 100,
  })).filter(x => x.price)
  const bids = [1,2,3].map(i => ({
    price: r[`bid_price_${i}`],
    vol:   r[`bid_volume_${i}`] ?? null,
    pct:   ((r[`bid_volume_${i}`] ?? 0) / maxVol) * 100,
  })).filter(x => x.price)
  const spread = asks.length && bids.length ? asks[asks.length - 1].price - bids[0].price : null
  return { asks, bids, spread }
})

const categories = ref([
  { name: 'MAKER1',    bg: '#FF8C00', fg: '#fff', active: true },
  { name: 'MAKER2',    bg: '#b50000', fg: '#fff', active: true },
  { name: 'TAKER1',    bg: '#00FF00', fg: '#000', active: true },
  { name: 'TAKER2',    bg: '#00a500', fg: '#000', active: true },
  { name: 'INFORMED1', bg: '#6A3FE5', fg: '#fff', active: true },
  { name: 'TOXIC',     bg: '#ff03f7', fg: '#fff', active: true },
  { name: 'ALGO',      bg: '#FFD700', fg: '#000', active: true },
])

const activeCategories = computed(() => categories.value.filter(c => c.active).map(c => c.name))

const loadRecentRuns = async () => {
  const { data } = await supabase.from('backtest_runs')
    .select('id, algo_name, round_id, status, total_pnl, created_at')
    .eq('year', '4')
    .order('created_at', { ascending: false })
    .limit(20)
  if (data) recentRuns.value = data
}

onMounted(loadRecentRuns)

const fetchProducts = async (id) => {
  if (!id) return
  const { data } = await supabase.from('backtest_runs').select('products_pnl').eq('id', id).single()
  if (data?.products_pnl) {
    const unique = Object.keys(data.products_pnl).filter(Boolean).sort()
    availableProducts.value = unique
    if (unique.length && !unique.includes(selectedProduct.value)) {
      selectedProduct.value = unique[0]
    }
  }
}

const runBacktest = async () => {
  isRunning.value = true
  try {
    const res = await $fetch(`${config.public.apiBase}/run/`, {
      method: 'POST',
      body: { algo_file: algoName.value, round: roundId.value, year: "4"}
    })
    activeTaskId.value = res.task_id
    pollStatus(res.task_id)
  } catch (e) {
    isRunning.value = false
  }
}

const handleFileUpload = async (event) => {
  const file = event.target.files[0]
  if (!file) return 

  const formData = new FormData()
  formData.append('file', file)
  formData.append('algo_file', algoName.value)
  formData.append('round', roundId.value)

  isRunning.value = true
  try {
    const res = await $fetch(`${config.public.apiBase}/upload-json` ,{
      method: 'POST',
      body: formData
    })
    activeTaskId.value = res.task_id
    pollStatus(res.task_id)
  } catch (e) {
    isRunning.value = false
  }
}

const pollStatus = (id) => {
  const timer = setInterval(async () => {
    const { data } = await supabase.from('backtest_runs').select('status').eq('id', id).single()

    if (data && (data.status === 'COMPLETED' || data.status === 'FAILED')) {
      clearInterval(timer)
      isRunning.value = false
      await loadRecentRuns()
      if (data.status === 'COMPLETED') {
        await fetchProducts(id)
      }
    }
  }, 2000)
}

const fetchTradeCounts = async (id) => {
  if (!id || !selectedProduct.value) return
  let tradeQuery = supabase.from('trades')
    .select('*', { count: 'exact', head: true })
    .eq('backtest_id', id)
    .eq('symbol', selectedProduct.value)
  let ownTradeQuery = supabase.from('trades')
    .select('*', { count: 'exact', head: true })
    .eq('backtest_id', id)
    .eq('symbol', selectedProduct.value)
    .or('buyer.eq.SUBMISSION,seller.eq.SUBMISSION')
  if (selectedDay.value !== 'all' && selectedDay.value !== '') {
    tradeQuery = tradeQuery.eq('day', selectedDay.value)
    ownTradeQuery = ownTradeQuery.eq('day', selectedDay.value)
  }
  try {
    const [{ count: trdCount }, { count: ownCount }] = await Promise.all([tradeQuery, ownTradeQuery])
    stats.value.trades = trdCount || 0
    stats.value.own    = ownCount || 0
  } catch (e) {}
}

watch(priceData, rows => {
  if (!rows?.length) return
  if (selectedDay.value === 'all' || selectedDay.value === '') {
    const lastPerDay = {}
    rows.forEach(row => { lastPerDay[row.day] = row.profit_and_loss ?? 0 })
    stats.value.pnl = Object.values(lastPerDay).reduce((a, b) => a + b, 0)
  } else {
    stats.value.pnl = rows[rows.length - 1].profit_and_loss ?? 0
  }
  timeRange.value = `${rows[0].timestamp} - ${rows[rows.length - 1].timestamp}`
})

const formatRunLabel = (run) => {
  const raw = run.created_at;
  if (!raw) return '—';

  try {
    const d = new Date(raw);
    const day = String(d.getDate()).padStart(2, '0');
    const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    
    const statusIcon = run.status === 'COMPLETED' ? '✓' : run.status === 'FAILED' ? '✗' : '…';
    const name = (run.algo_name || 'algo').replace('.py', '').substring(0, 8).padEnd(8);
    
    return `${name} | R${run.round_id} | ${statusIcon} | ${day}@${hm}`;
  } catch (e) {
    // Fallback just shows the most relevant 15 chars if everything explodes
    return raw.replace('2026-', '').substring(0, 15);
  }
};

const formattedRuns = computed(() => {
  return recentRuns.value.map(r => ({
    id: r.id,
    label: formatRunLabel(r)
  }))
})

watch(activeTaskId, async (newId) => {
  if (!newId) return
  await fetchProducts(newId)
}, { immediate: true })

watch([activeTaskId, selectedProduct, selectedDay], ([id, product, day]) => {
  loadBacktestData(id, product, day)
  fetchTradeCounts(id)
}, { immediate: true })
</script>

<style scoped>

.app-wrapper {
  width: calc(100vw);
}

.mono-select {
  font-family: 'IBM Plex Mono', 'Courier New', monospace !important;
  font-size: 11px !important;
  letter-spacing: -0.3px;
}
.raw-select {
  width: 100%;
  background: #fff;
  border: 1px solid #ccc;
  padding: 2px 4px;
}
.ind-dropdown {
  position: relative;
}
.ind-trigger {
  cursor: pointer;
  user-select: none;
}
.ind-options {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #ccc;
  border-top: none;
  z-index: 20;
  padding: 4px 6px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11px;
}
.bx {
  display: flex;
  flex-direction: row;
}
.bx div {
  width: 50%;
}
.ob-widget {
  border: 1px solid #ddd;
  background: #fff;
  font-size: 10px;
  overflow: hidden;
}
.ob-row {
  display: grid;
  grid-template-columns: 22px 1fr 40px;
  align-items: center;
  gap: 2px;
  padding: 1px 3px;
}
.ob-v { color: #999; text-align: right; }
.ob-p { text-align: right; font-weight: 600; }
.ob-ask .ob-p { color: #cc1111; }
.ob-bid .ob-p { color: #1111cc; }
.ob-bar-track { height: 5px; background: #f0f0f0; }
.ob-bar { height: 100%; }
.ob-bar-ask { background: rgba(200,0,0,0.25); }
.ob-bar-bid { background: rgba(0,0,200,0.25); }
.ob-spread-line {
  text-align: center;
  font-size: 9px;
  color: #aaa;
  border-top: 1px solid #eee;
  border-bottom: 1px solid #eee;
  padding: 1px 0;
  letter-spacing: 0.3px;
}
.ob-empty {
  border: 1px solid #ddd;
  background: #fff;
  font-size: 9px;
  color: #bbb;
  padding: 5px 4px;
  text-align: center;
}
</style>