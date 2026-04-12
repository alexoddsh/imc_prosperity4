// Single source of truth for per-(backtest, product, day) data.
// Fetches prices/trades/internal once; charts consume via props instead
// of each firing their own Supabase queries.
export const useBacktestData = () => {
  const supabase = useSupabaseClient()
  const { fetchAll } = useFetchAll()

  const priceData    = ref(null)
  const tradeData    = ref(null)
  const internalData = ref(null)
  const loading      = ref(false)
  let reqId = 0

  const load = async (taskId, product, day) => {
    if (!taskId || !product || day === '' || day == null) {
      priceData.value = null
      tradeData.value = null
      internalData.value = null
      return
    }
    const myReq = ++reqId
    loading.value = true

    let priceQ = supabase.from('prices')
      .select('*')
      .eq('backtest_id', taskId)
      .eq('product', product)

    let tradeQ = supabase.from('trades')
      .select('*')
      .eq('backtest_id', taskId)
      .eq('symbol', product)

    let internalQ = supabase.from('internal')
      .select('*')
      .eq('backtest_id', taskId)
      .eq('product', product)
      .neq('order_quantity', 0)

    if (day !== 'all') {
      priceQ    = priceQ.eq('day', day)
      tradeQ    = tradeQ.eq('day', day)
      internalQ = internalQ.eq('day', day)
    }

    priceQ    = priceQ.order('timestamp', { ascending: true })
    tradeQ    = tradeQ.order('timestamp', { ascending: true })
    internalQ = internalQ.order('timestamp', { ascending: true })

    const [p, t, i] = await Promise.all([
      fetchAll(() => priceQ),
      fetchAll(() => tradeQ),
      fetchAll(() => internalQ),
    ])

    if (myReq !== reqId) return
    priceData.value    = p
    tradeData.value    = t
    internalData.value = i
    loading.value = false
  }

  return { priceData, tradeData, internalData, loading, load }
}
