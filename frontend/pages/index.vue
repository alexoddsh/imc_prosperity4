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
        />
      </div>
      <div class="sub-chart">
        <PnLChart 
        :taskId="activeTaskId" 
        :product="selectedProduct"
        :day="selectedDay"
        />
      </div>
      <div class="sub-chart">
        <PositionChart 
        :taskId="activeTaskId" 
        :product="selectedProduct" 
        :day="selectedDay"
        />
      </div>
    </main>

    <aside class="control-sidebar">
      <div class="info-box">
        <b>{{ selectedProduct || '—' }}</b> | {{ timeRange }}<br>
        trades: {{ stats.trades }} (own: {{ stats.own }})<br>
        PnL: <b>{{ stats.pnl.toFixed(0) }}</b>
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
        <div class="checkbox-list">
          <label v-for="opt in ['Mid', 'WallMid1', 'WallMid2']" :key="opt">
            <input type="checkbox" :value="opt" v-model="selectedInd"> {{ opt }}
          </label>
        </div>
      </div>

      <div>
        <span class="sl">order book</span>
        <div class="checkbox-list">
          <label v-for="lvl in [1, 2, 3]" :key="lvl">
            <input type="checkbox" :value="lvl" v-model="obLevels"> L{{ lvl }}
          </label>
        </div>
      </div>

      <div>
        <span class="sl">normalize</span>
        <select v-model="normBy" class="raw-select">
          <option value="None">None</option>
          <option v-for="opt in ['Mid', 'WallMid1', 'WallMid2']" :key="opt">{{ opt }}</option>
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

      <div class="error-box" style="margin-top: auto;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:3px;">
          <span class="sl" style="margin-bottom:0;">errors</span>
          <span v-if="errors.length" class="sl" style="margin-bottom:0; cursor:pointer;" @click="errors=[]">clear</span>
        </div>
        <div class="error-list">
          <div v-if="!errors.length" style="color:#bbb; font-size:10px;">—</div>
          <div v-for="(e, i) in errors" :key="i" class="error-entry">
            <span style="color:#999;">{{ e.t }}</span> {{ e.msg }}
          </div>
        </div>
      </div>

      <div style="margin-top: 0;">
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
const supabase = useSupabaseClient()
const { fetchAll } = useFetchAll()

const activeTaskId = ref('')
const isRunning = ref(false)
const algoName = ref('algo.py')
const roundId = ref('0')
const recentRuns = ref([])
const availableProducts = ref([])
const selectedProduct = ref('')
const selectedDay = ref('')
const timeRange = ref('-')
const selectedInd = ref([])
const normBy = ref('None')
const obLevels = ref([1])

const stats    = ref({ trades: 0, own: 0, pnl: 0 })
const qtyRange = ref([1, 100])
const errors = ref([])

const pushError = (msg) => {
  errors.value.push({ msg, t: new Date().toLocaleTimeString() })
  if (errors.value.length > 50) errors.value.shift()
}

const categories = ref([
  { name: 'MAKER1',    bg: '#FF8C00', fg: '#fff', active: true },
  { name: 'TAKER1',    bg: '#00FF00', fg: '#000', active: true },
  { name: 'INFORMED1', bg: '#FF0000', fg: '#fff', active: true },
  { name: 'TOXIC',     bg: '#ff03f7', fg: '#fff', active: true },
  { name: 'ALGO',      bg: '#FFD700', fg: '#000', active: true },
])

const activeCategories = computed(() => categories.value.filter(c => c.active).map(c => c.name))

const loadRecentRuns = async () => {
  const { data } = await supabase.from('backtest_runs')
    .select('id, algo_name, round_id, status, total_pnl, created_at')
    .order('created_at', { ascending: false })
    .limit(20)
  if (data) recentRuns.value = data
}

onMounted(loadRecentRuns)

const fetchProducts = async (id) => {
  if (!id) return
  const { data } = await supabase.from('prices').select('product').eq('backtest_id', id)
  if (data) {
    const unique = [...new Set(data.map(r => r.product))].filter(Boolean).sort()
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
      body: { algo_file: algoName.value, round: roundId.value }
    })
    activeTaskId.value = res.task_id
    pollStatus(res.task_id)
  } catch (e) {
    pushError(`run: ${e?.message ?? e}`)
    isRunning.value = false
  }
}

const pollStatus = (id) => {
  let linesShown = 0
  errors.value = []

  const timer = setInterval(async () => {
    const [{ data }, logsRes] = await Promise.all([
      supabase.from('backtest_runs').select('status').eq('id', id).single(),
      $fetch(`${config.public.apiBase}/logs/${id}`).catch(() => null),
    ])

    if (logsRes?.lines) {
      const newLines = logsRes.lines.slice(linesShown)
      newLines.forEach(line => pushError(line))
      linesShown = logsRes.lines.length
    }

    if (data && (data.status === 'COMPLETED' || data.status === 'FAILED')) {
      clearInterval(timer)
      isRunning.value = false
      await loadRecentRuns()
      if (data.status === 'COMPLETED') {
        await fetchProducts(id)
        fetchSummaryStats(id)
      }
    }
  }, 2000)
}

const fetchSummaryStats = async (id) => {
  if (!id || !selectedProduct.value) return
  
  let priceQuery = supabase.from('prices')
    .select('timestamp, profit_and_loss, day')
    .eq('backtest_id', id)
    .eq('product', selectedProduct.value)

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
    priceQuery = priceQuery.eq('day', selectedDay.value)
    tradeQuery = tradeQuery.eq('day', selectedDay.value)
    ownTradeQuery = ownTradeQuery.eq('day', selectedDay.value)
  }

  try {
    const [rows, { count: trdCount }, { count: ownCount }] = await Promise.all([
      fetchAll(() => priceQuery.order('day').order('timestamp')),
      tradeQuery,
      ownTradeQuery,
    ])

    if (rows?.length) {
      if (selectedDay.value === 'all' || selectedDay.value === '') {
        const lastPerDay = {}
        rows.forEach(row => { lastPerDay[row.day] = row.profit_and_loss ?? 0 })
        stats.value.pnl = Object.values(lastPerDay).reduce((a, b) => a + b, 0)
      } else {
        stats.value.pnl = rows[rows.length - 1].profit_and_loss ?? 0
      }
      timeRange.value = `${rows[0].timestamp} - ${rows[rows.length - 1].timestamp}`
    }
    
    stats.value.trades = trdCount || 0
    stats.value.own    = ownCount || 0
  } catch (e) { pushError(`stats: ${e?.message ?? e}`) }
}

const formatRunLabel = (run) => {
  const raw = run.created_at;
  if (!raw) return '—';

  try {
    const normalized = raw.replace('T', ' '); 
    const parts = normalized.split(' '); 
    
    const dateParts = parts[0].split('-'); 
    const day = dateParts[2] || '??';
    
    const timePart = parts[1] || '';
    const hm = timePart.substring(0, 5) || '??:??';
    
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
  fetchSummaryStats(newId)
})
watch(selectedProduct, () => fetchSummaryStats(activeTaskId.value))
watch(selectedDay, () => {fetchSummaryStats(activeTaskId.value)})
</script>

<style scoped>

.app-wrapper {
  margin-left: 5px;
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
</style>