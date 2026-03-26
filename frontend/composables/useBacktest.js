export const useBacktest = () => {
  const isRunning = ref(false)
  const lastTaskId = ref(null)
  const supabase = useSupabaseClient()

  const pollStatus = async (taskId) => {
    const { data, error } = await supabase
      .from('backtest_runs')
      .select('status')
      .eq('id', taskId)
      .single()

    if (data?.status === 'COMPLETED' || data?.status === 'FAILED') {
      isRunning.value = false
      return true
    }
    return false
  }

  const startBacktest = async (algoName, roundId) => {
    isRunning.value = true
    try {
      const response = await $fetch(`http://127.0.0.1:8000/run/${algoName}`, {
        method: 'POST',
        query: { round_id: roundId }
      })
      
      lastTaskId.value = response.task_id
      
      // Start polling every 2 seconds
      const interval = setInterval(async () => {
        const finished = await pollStatus(response.task_id)
        if (finished) clearInterval(interval)
      }, 2000)

      return response.task_id
    } catch (err) {
      console.error("Failed to trigger backtest:", err)
      isRunning.value = false
    }
  }

  return { startBacktest, isRunning, lastTaskId }
}