<template>
  <div class="app-wrapper">
    <main class="chart-area">
      <div v-if="!activeTaskId" class="r5-empty">— select a backtest run —</div>
      <div v-else-if="!productsInCategory.length" class="r5-empty">
        — no products in <b>{{ selectedCategory || '?' }}</b> for this run —
      </div>
      <div v-else class="r5-grid" :style="gridStyle">
        <CategoryProductChart
          v-for="p in productsInCategory"
          :key="p"
          :taskId="activeTaskId"
          :product="p"
          :day="selectedDay || (availableDays[0] ?? '')"
          :style="{ height: cellHeight + 'px' }"
        />
      </div>
    </main>

    <aside class="control-sidebar">
      <div class="info-box">
        <b>round 5</b><br>
        category: <b>{{ selectedCategory || '—' }}</b><br>
        products: <b>{{ productsInCategory.length }}</b>
      </div>

      <div>
        <span class="sl">run history</span>
        <select v-model="activeTaskId" class="raw-select mono-select">
          <option value="" disabled>— select run —</option>
          <option v-for="r in formattedRuns" :key="r.id" :value="r.id">
            {{ r.label }}
          </option>
        </select>
      </div>

      <div>
        <span class="sl">category ({{ availableCategories.length }})</span>
        <select v-model="selectedCategory" class="raw-select" :disabled="!availableCategories.length">
          <option value="" disabled>— select category —</option>
          <option v-for="c in availableCategories" :key="c" :value="c">
            {{ c }} ({{ productsByCategory[c].length }})
          </option>
        </select>
      </div>

      <div>
        <span class="sl">day</span>
        <select v-model="selectedDay" class="raw-select" :disabled="!availableDays.length">
          <option value="" disabled>— select day —</option>
          <option v-if="availableDays.length" value="all">All</option>
          <option v-for="d in availableDays" :key="d" :value="d">Day {{ d }}</option>
        </select>
      </div>

      <div>
        <span class="sl">grid columns</span>
        <select v-model.number="gridCols" class="raw-select">
          <option v-for="n in [1,2,3,4,5]" :key="n" :value="n">{{ n }}</option>
        </select>
      </div>

      <div>
        <span class="sl">cell height ({{ cellHeight }}px)</span>
        <input type="range" min="200" max="900" step="20" v-model.number="cellHeight" class="raw-input" style="padding:0;" />
      </div>

      <div style="margin-top:auto; font-size:10px; color: var(--text-dim); line-height:1.4;">
        same price chart, one per product in the selected category. each cell pulls its own data.
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'

definePageMeta({ path: '/prosperity4/round5' })

const route = useRoute()
const supabase = useSupabaseClient()
const { fetchAll } = useFetchAll()

const ALL_PRODUCTS = [
  'GALAXY_SOUNDS_DARK_MATTER', 'GALAXY_SOUNDS_BLACK_HOLES', 'GALAXY_SOUNDS_PLANETARY_RINGS', 'GALAXY_SOUNDS_SOLAR_WINDS', 'GALAXY_SOUNDS_SOLAR_FLAMES',
  'SLEEP_POD_SUEDE', 'SLEEP_POD_LAMB_WOOL', 'SLEEP_POD_POLYESTER', 'SLEEP_POD_NYLON', 'SLEEP_POD_COTTON',
  'MICROCHIP_CIRCLE', 'MICROCHIP_OVAL', 'MICROCHIP_SQUARE', 'MICROCHIP_RECTANGLE', 'MICROCHIP_TRIANGLE',
  'PEBBLES_XS', 'PEBBLES_S', 'PEBBLES_M', 'PEBBLES_L', 'PEBBLES_XL',
  'ROBOT_VACUUMING', 'ROBOT_MOPPING', 'ROBOT_DISHES', 'ROBOT_LAUNDRY', 'ROBOT_IRONING',
  'UV_VISOR_YELLOW', 'UV_VISOR_AMBER', 'UV_VISOR_ORANGE', 'UV_VISOR_RED', 'UV_VISOR_MAGENTA',
  'TRANSLATOR_SPACE_GRAY', 'TRANSLATOR_ASTRO_BLACK', 'TRANSLATOR_ECLIPSE_CHARCOAL', 'TRANSLATOR_GRAPHITE_MIST', 'TRANSLATOR_VOID_BLUE',
  'PANEL_1X2', 'PANEL_2X2', 'PANEL_1X4', 'PANEL_2X4', 'PANEL_4X4',
  'OXYGEN_SHAKE_MORNING_BREATH', 'OXYGEN_SHAKE_EVENING_BREATH', 'OXYGEN_SHAKE_MINT', 'OXYGEN_SHAKE_CHOCOLATE', 'OXYGEN_SHAKE_GARLIC',
  'SNACKPACK_CHOCOLATE', 'SNACKPACK_VANILLA', 'SNACKPACK_PISTACHIO', 'SNACKPACK_STRAWBERRY', 'SNACKPACK_RASPBERRY',
]

// Category prefixes — longest first so e.g. GALAXY_SOUNDS wins over GALAXY.
const CATEGORY_PREFIXES = [
  'GALAXY_SOUNDS', 'SLEEP_POD', 'MICROCHIP', 'PEBBLES', 'ROBOT',
  'UV_VISOR', 'TRANSLATOR', 'PANEL', 'OXYGEN_SHAKE', 'SNACKPACK',
]

const categoryFor = (product) => {
  for (const c of CATEGORY_PREFIXES) {
    if (product.startsWith(c + '_') || product === c) return c
  }
  return 'OTHER'
}

const activeTaskId   = ref(route.query.taskId || '')
const recentRuns     = ref([])
const runProducts    = ref([])
const availableDays  = ref([])
const selectedDay    = ref('')
const selectedCategory = ref('')
const gridCols       = ref(3)
const cellHeight     = ref(520)

const productsByCategory = computed(() => {
  const groups = {}
  // Use both the run's products + the canonical list, intersected.
  // If the run has products we don't know about, still group them.
  const set = new Set(runProducts.value.length ? runProducts.value : ALL_PRODUCTS)
  for (const p of set) {
    const c = categoryFor(p)
    ;(groups[c] ||= []).push(p)
  }
  for (const c of Object.keys(groups)) groups[c].sort()
  return groups
})

const availableCategories = computed(() => {
  return CATEGORY_PREFIXES.filter(c => productsByCategory.value[c]?.length)
    .concat(productsByCategory.value.OTHER ? ['OTHER'] : [])
})

const productsInCategory = computed(() => {
  if (!selectedCategory.value) return []
  return productsByCategory.value[selectedCategory.value] ?? []
})

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${gridCols.value}, minmax(0, 1fr))`,
}))

const loadRecentRuns = async () => {
  const { data } = await supabase.from('backtest_runs')
    .select('id, algo_name, round_id, status, total_pnl, created_at')
    .eq('year', '4')
    .order('created_at', { ascending: false })
    .limit(20)
  if (data) recentRuns.value = data
}

onMounted(loadRecentRuns)

const fetchRunMeta = async (id) => {
  if (!id) {
    runProducts.value = []
    availableDays.value = []
    return
  }
  const { data } = await supabase.from('backtest_runs').select('products_pnl').eq('id', id).single()
  runProducts.value = data?.products_pnl ? Object.keys(data.products_pnl).filter(Boolean).sort() : []
  // Two index probes for min/max day, then assume contiguous. Avoids scanning
  // the entire prices slice (1.7M rows per backtest) just to find distinct days.
  const [{ data: minRow }, { data: maxRow }] = await Promise.all([
    supabase.from('prices').select('day').eq('backtest_id', id).order('day', { ascending: true }).limit(1).maybeSingle(),
    supabase.from('prices').select('day').eq('backtest_id', id).order('day', { ascending: false }).limit(1).maybeSingle(),
  ])
  const days = (minRow && maxRow)
    ? Array.from({ length: maxRow.day - minRow.day + 1 }, (_, i) => minRow.day + i)
    : []
  availableDays.value = days
  if (days.length && !days.includes(selectedDay.value) && selectedDay.value !== 'all') {
    selectedDay.value = days[0]
  }
}

watch(activeTaskId, fetchRunMeta, { immediate: true })

// Auto-pick first available category once products land.
watch(availableCategories, (cats) => {
  if (cats.length && !cats.includes(selectedCategory.value)) {
    selectedCategory.value = cats[0]
  }
})

const formatRunLabel = (run) => {
  const raw = run.created_at
  if (!raw) return '—'
  try {
    const d = new Date(raw)
    const day = String(d.getDate()).padStart(2, '0')
    const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    const statusIcon = run.status === 'COMPLETED' ? '✓' : run.status === 'FAILED' ? '✗' : '…'
    const name = (run.algo_name || 'algo').replace('.py', '').substring(0, 8).padEnd(8)
    return `${name} | R${run.round_id} | ${statusIcon} | ${day}@${hm}`
  } catch (e) {
    return raw.replace('2026-', '').substring(0, 15)
  }
}

const formattedRuns = computed(() =>
  recentRuns.value.map(r => ({ id: r.id, label: formatRunLabel(r) }))
)
</script>

<style scoped>
.r5-grid {
  display: grid;
  gap: 4px;
  padding: 4px;
  height: 100%;
  width: 100%;
  overflow-y: auto;
  background: #f0f0f0;
  align-content: start;
}
.r5-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 12px;
  color: var(--text-dim);
}
.mono-select {
  font-family: 'IBM Plex Mono', 'Courier New', monospace !important;
  font-size: 11px !important;
  letter-spacing: -0.3px;
}
</style>
