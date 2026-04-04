// Supabase PostgREST hard-caps rows at max_rows (default 1000).
// Fetches first page, then fires remaining pages in parallel batches of 10.
export const useFetchAll = () => {
  const fetchAll = async (queryFn, pageSize = 1000) => {
    const { data: first, error } = await queryFn().range(0, pageSize - 1)
    if (error || !first?.length) return []
    if (first.length < pageSize) return first

    const result = [...first]
    let batchStart = 1
    const BATCH = 10

    while (true) {
      const pages = await Promise.all(
        Array.from({ length: BATCH }, (_, i) => {
          const page = batchStart + i
          return queryFn()
            .range(page * pageSize, (page + 1) * pageSize - 1)
            .then(({ data }) => data ?? [])
        })
      )
      let done = false
      for (const page of pages) {
        if (!page.length) { done = true; break }
        result.push(...page)
        if (page.length < pageSize) { done = true; break }
      }
      if (done) break
      batchStart += BATCH
    }
    return result
  }
  return { fetchAll }
}
