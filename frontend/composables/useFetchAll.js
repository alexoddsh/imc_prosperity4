// Supabase PostgREST hard-caps rows at max_rows (default 1000).
// This paginates through all pages using .range() until exhausted.
export const useFetchAll = () => {
  const fetchAll = async (queryFn, pageSize = 1000) => {
    const results = []
    let from = 0
    while (true) {
      const { data, error } = await queryFn().range(from, from + pageSize - 1)
      if (error || !data || data.length === 0) break
      results.push(...data)
      if (data.length < pageSize) break
      from += pageSize
    }
    return results
  }
  return { fetchAll }
}
