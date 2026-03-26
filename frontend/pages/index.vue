<template>
  <div class="app-wrapper">
    <main class="chart-area">
      <div class="main-chart">
        <PriceChart
          :taskId="activeTaskId"
          :product="selectedProduct"
          :indicators="selectedInd"
          :normalize="normBy"
          :activeCategories="activeCategories"
        />
      </div>
      <div class="sub-chart">
        <PnLChart :taskId="activeTaskId" :product="selectedProduct" />
      </div>
      <div class="sub-chart">
        <PositionChart :taskId="activeTaskId" :product="selectedProduct" />
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
        <select v-model="activeTaskId" class="raw-select" style="margin-bottom:4px;">
          <option value="" disabled>— select run —</option>
          <option v-for="r in recentRuns" :key="r.id" :value="r.id">{{ r.algo_name }} / r{{ r.round_id }}</option>
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
        <span class="sl">indicators</span>
        <div class="checkbox-list">
          <label v-for="opt in ['Mid', 'WallMid1', 'WallMid2']" :key="opt">
            <input type="checkbox" :value="opt" v-model="selectedInd"> {{ opt }}
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

      <div style="margin-top: auto;">
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
const supabase = useSupabaseClient()

const activeTaskId = ref('')
const isRunning = ref(false)
const algoName = ref('algo.py')
const roundId = ref('0')
const recentRuns = ref([])
const availableProducts = ref([])
const selectedProduct = ref('')
const timeRange = ref('-')
const selectedInd = ref([])
const normBy = ref('None')

const stats = ref({ trades: 0, own: 0, pnl: 0 })

const categories = ref([
  { name: 'M', bg: '#FF8C00', fg: '#fff', active: true },
  { name: 'S', bg: '#00FF00', fg: '#000', active: true },
  { name: 'B', bg: '#FF8C00', fg: '#fff', active: true },
  { name: 'I', bg: '#FF0000', fg: '#fff', active: true },
  { name: 'F', bg: '#FFD700', fg: '#000', active: true },
])

const activeCategories = computed(() => categories.value.filter(c => c.active).map(c => c.name))

const loadRecentRuns = async () => {
  const { data } = await supabase.from('backtest_runs')
    .select('id, algo_name, round_id, status, total_pnl')
    .order('created_at', { ascending: false })
    .limit(20)
  if (data) recentRuns.value = data
}

onMounted(loadRecentRuns)

const fetchProducts = async (id) => {
  if (!id) return
  const { data } = await supabase.from('indicators').select('product').eq('backtest_id', id)
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
    console.error(e)
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
      await fetchProducts(id)
      fetchSummaryStats(id)
    }
  }, 2000)
}

const fetchSummaryStats = async (id) => {
  if (!id || !selectedProduct.value) return
  const { data: ind } = await supabase.from('indicators')
    .select('timestamp, profit_and_loss')
    .eq('backtest_id', id)
    .eq('product', selectedProduct.value)
    .order('timestamp', { ascending: true })
    .limit(10000)
  const { count: trdCount } = await supabase.from('trades').select('*', { count: 'exact', head: true }).eq('backtest_id', id)
  const { count: ownCount } = await supabase.from('trades').select('*', { count: 'exact', head: true }).eq('backtest_id', id).or('buyer.eq.SUBMISSION,seller.eq.SUBMISSION')

  if (ind && ind.length) {
    timeRange.value = `${ind[0].timestamp} - ${ind[ind.length - 1].timestamp}`
    stats.value.pnl = ind[ind.length - 1].profit_and_loss ?? 0
  }
  stats.value.trades = trdCount || 0
  stats.value.own = ownCount || 0
}

watch(activeTaskId, async (newId) => {
  if (!newId) return
  await fetchProducts(newId)
  fetchSummaryStats(newId)
})
watch(selectedProduct, () => fetchSummaryStats(activeTaskId.value))
</script>