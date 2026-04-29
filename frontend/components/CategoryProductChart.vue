<template>
  <div class="cpc-wrap">
    <div class="cpc-header">
      <span class="cpc-name">{{ product }}</span>
      <span class="cpc-pnl" v-if="pnl != null" :style="{ color: pnl >= 0 ? '#0a7d0a' : '#cc1111' }">
        {{ pnl.toFixed(0) }}
      </span>
    </div>
    <div class="cpc-chart">
      <PriceChart
        :taskId="taskId"
        :product="product"
        :day="day"
        :indicators="[]"
        normalize="None"
        :activeCategories="[]"
        :activeTraders="null"
        :qtyRange="[1, 100]"
        :obLevels="[1]"
        :showAlgoOb="false"
        :priceData="priceData"
        :tradeData="null"
        :internalData="null"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  taskId: { type: String, required: true },
  product: { type: String, required: true },
  day: { type: [String, Number], required: true },
})

const supabase = useSupabaseClient()
const { fetchAll } = useFetchAll()

const priceData = ref(null)
let reqId = 0

const loadPrices = async () => {
  if (!props.taskId || !props.product || props.day === '' || props.day == null) {
    priceData.value = null
    return
  }
  const myReq = ++reqId
  // Only the columns this view actually renders. Selecting `*` on prices
  // drags ~25 columns through PostgREST JSON serialization for nothing.
  let q = supabase.from('prices')
    .select('timestamp,day,ask_price_1,bid_price_1,profit_and_loss')
    .eq('backtest_id', props.taskId)
    .eq('product', props.product)
  if (props.day !== 'all') q = q.eq('day', props.day)
  q = q.order('timestamp', { ascending: true })
  const data = await fetchAll(() => q)
  if (myReq !== reqId) return
  priceData.value = data
}

watch([() => props.taskId, () => props.product, () => props.day], loadPrices, { immediate: true })

const pnl = computed(() => {
  const rows = priceData.value
  if (!rows?.length) return null
  if (props.day === 'all' || props.day === '') {
    const lastPerDay = {}
    rows.forEach(row => { lastPerDay[row.day] = row.profit_and_loss ?? 0 })
    return Object.values(lastPerDay).reduce((a, b) => a + b, 0)
  }
  return rows[rows.length - 1].profit_and_loss ?? 0
})
</script>

<style scoped>
.cpc-wrap {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color);
  background: #fff;
  height: 100%;
  min-height: 0;
}
.cpc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 6px;
  border-bottom: 1px solid var(--border-color);
  background: #f8f8f8;
  font-size: 10px;
  font-weight: 600;
  flex: 0 0 auto;
}
.cpc-name {
  letter-spacing: -0.2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cpc-pnl {
  font-weight: 700;
  margin-left: 6px;
}
.cpc-chart {
  flex: 1 1 auto;
  min-height: 0;
  position: relative;
}
</style>
