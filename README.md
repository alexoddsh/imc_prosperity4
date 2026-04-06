# IMC4 Repo

## Installation
FIRST, if you are going to use a requirements file then please fucking add it to gitignore! But i highly suggest 
just using the superior "pipenv" since that is best for this project and already in place for you to download!

To get the backend and backtester running locally, follow these steps. Note that the system relies on a specific virtual environment and binary executable path.

### 1. Clone & Environment Setup
Ensure you have `pipenv` installed to manage the specific virtual environment used by the sub-processes.
```bash
# Install dependencies
pipenv install

# Environment variables
cp .env.example .env
```
**Note** I didn't add to gitignore, please do so after you have copied the original. Also you have been invited to supabase. 

### 2. Binary Exec Path
The system uses a custom binary prosperity4btx located in your virtualenv. Main.py reads this path from your .env file. So you after installing the executable (which is already a req in the pipfile) you need to find its path and add to .env. Read about how the backtester works at:
- https://github.com/Xeeshan85/imc-prosperity-4-backtester

## Starting... & Using
The backend uses FastAPI to manage simulation tasks. Start the server with: "uvicorn main:app --reload" or however you want to run it. Then start the frontend as usual with "npm run dev". Code your algo in the *backend/algos* folder. Try to name them something unique. So to be 100% I scrapped the vercel + railway hosting idea, just adds unneccessary lag 
when we can both easily run it locally for ourselves. The only main thing to think about as usual is to not push incompatible stuff (obvs) so generally these are not to be touched at all:

1. `main.py`
2. `core/parser.py` (first half)
3. `Logger.flush()` output format (the JSON shape that `main.py` and `inter.py` depend on)
4. existing frontend implementation

### Two ways to get data in
- **Run backtester** (`POST /run/`) — triggers the `prosperity4btx` binary with your algo file and a round ID. Results are streamed and auto-parsed.
- **Upload official log** (`POST /upload-json`) — upload a `.log` file downloaded from the Prosperity website (JSON format). Skips the backtester entirely, parser runs directly for computations etc and then into the DB. Small note, frontend is not a fucking SaaS app, when you upload this process starts automatically directly, no "are you sure xx"

**Adding columns in Supabase?** Rows accumulate QUICKLY so generally two main points. A) delete data from scrap runs B) (should be done auto see below) use alembic migs or default values in code when adding columns as to not nuke any previous runs.

### Automatic cleanup job (`backend/cleanup.py`)
Runs once on startup and then every 30 minutes in the background. It deletes from `backtest_runs` — child rows in `trades`, `prices`, and `internal` are removed automatically via `ON DELETE CASCADE`. Tunables for this are constants at the top of the file.

| Rule | What gets deleted |
| :--- | :--- |
| Failed runs | Any run with `status = 'FAILED'` older than 15 min |
| Low PnL | Completed runs with `total_pnl < 20` (or `NULL`) older than 15 min |
| Stuck pending | `PENDING` runs older than 10 min (backtest never finished) |
| Previous-round bottom | For every round except the most recent, keeps only the top 20 by PnL (15 min grace) |
| Global top-N | For runs older than 3 hours, keeps only the top 100 globally |

## Dev - Simulation and Logs 
- `main.py` -> runs the prosperity4btx backtester executable against the specified algo file in */backend/algos*. Two log files are produced per run, both written into */backend/logs/*:
  - **`{task_id}.log`** — written by the prosperity4btx binary itself (via `--out`). Contains the structured Activities log (prices CSV) and Trade History (trades JSON) that the parser reads.
  - **`{task_id}_stream.log`** — written by `main.py` by capturing every line of stdout from the subprocess. Contains the raw JSON lines printed by `logger.flush()` each tick (each with `sandboxLog` and `lambdaLog`), plus non-JSON status lines emitted by the backtester. This is what `inter.py` reads for internal data.

The Logger class (defined in each algo file — not `datamodel.py` since it is our own version and therefore is not defined by prosperity) accumulates prints in memory and flushes a single JSON line to stdout at the end of each `run()` call. `main.py` picks that up and decides what to show in the terminal vs. write silently to the stream log. So to summarize the main idea is:

| Channel | Destination | Purpose | Format | Best Practice |
| :--- | :--- | :--- | :--- | :--- |
| **`self.logger.print()`** | `{task_id}_stream.log` + terminal | **Humans.** Real-time debugging and terminal milestones. | Plain Text / String | **Cannot coexist with `[DATA]` on the same tick** (see below). Only use on ticks where you are NOT logging `[DATA]`. To be clear this is essentially useless currently, IF you want debug prints use a normal print (see below) if you want prints that persist in the logs use the DATA version below. |
| **`self.logger.print("[DATA] ...")`** | `{task_id}_stream.log` only (silent) | **Post-run parsing.** Store structured data (orders, signals) per timestamp for offline analysis. | `[DATA] ` prefix + JSON string | **Use this every tick.** The `[DATA]` prefix is filtered from terminal output by `main.py` but is written to the stream log. **CRITICAL: this must be the ONLY `self.logger.print()` call on any tick where it runs.** `inter.py` parses internal data by stripping `[DATA] ` from the entire `sandboxLog` and calling `json.loads()` — mixing in any other print on the same tick corrupts the JSON and crashes the parser. |
| **`traderData`** | Internal State / `lambdaLog` | **The Machine.** Persistent memory to pass variables to the next round. | JSON | **50k char limit in competition.** Only store what the bot needs to remember between ticks. Do NOT use this for logging. |
| **`print()`** | raw stdout / terminal | **Terminal only, not in stream log.** Raw Python `print()` does appear in the terminal (via the backtester's `--print` flag), but is **not** written to `{task_id}_stream.log` and cannot be post-parsed. | — |  Use to print debug etc as normal, careful not to crash terminal... |

When writing your `run` method, follow this sequence to ensure the backtester captures everything correctly:

1. **Read Memory**: 
   `memory = json.loads(state.traderData) if state.traderData else {}`

2. **Build orders, compute signals, etc.**

3. **Log `[DATA]`** (the only `self.logger.print()` call per tick): 
   `self.logger.print(f"[DATA] {json.dumps({str(state.timestamp): logs})}")`

4. **Save for Algo (Memory)**: 
   `traderData = json.dumps(memory)`

5. **Output at EOF run() method**: 
   `self.logger.flush(state, result, conversions, traderData)`
   `return result, conversions, traderData`

Example (see `algos/version4.py` for a full working version):

```python
def run(self, state: TradingState):
    memory = json.loads(state.traderData) if state.traderData else {}
    result = {}
    logs = []

    # ... build orders, compute signals ...

    # ONE logger.print per tick — only [DATA], nothing else
    self.logger.print(f"[DATA] {json.dumps({str(state.timestamp): logs})}")

    traderData = json.dumps(memory)
    self.logger.flush(state, result, conversions, traderData)
    return result, conversions, traderData
```

`inter.py` parses the `{task_id}_stream.log` after the run: it reads each JSON line, extracts `sandboxLog`, strips the `[DATA] ` prefix, and `json.loads()` the remainder. This is why only one `self.logger.print()` call is allowed per tick.

The Logger class is **not** in `datamodel.py` — it is copy-pasted directly into each algo file. Check any existing algo (e.g. `algos/version1.py`) to see the full implementation.

## Dev - Computations
- `core/parser.py` handles both input modes. For the backtester it reads the `.log` file + `_stream.log`. For official uploads it reads the JSON directly. Either way it produces the same three DataFrames: `prices`, `trades`, `internal` — so everything downstream is identical.

The `internal` df is built from `[DATA]` log entries via `core/inter.py` and stored in the Supabase `internal` table.

The second half calls all the **pre computations** defined in */backend/core*. These computations modify the created
dataframe BEFORE inserting in the DB which is done at the end, this as it is a lot easier to NOT have to modify any
existing data in Supabase. This keeps the flow coherently tied only to pandas/np mgmt and database data is always good. **NOTE** here that all computations return a bool `True` **IF and ONLY IF** the full computations complete perfectly. And only **IF** all computations return `True` do we persist a run in the db, otherwise it is discarded.

Current computation pipeline (in order):
```python
# prices pre-compute
normalizer.compute_wallmid1(product, prices)    # core/normalizer.py
normalizer.compute_wallmid2(product, prices)
normalizer.compute_wallmid_ma(product, prices)  # rolling MA of wallmid2

# trades pre-compute
classification.compute_classes(product, prices, trades)  # core/classification.py
position.compute_position(product, trades)               # core/position.py
```

Then all three tables are inserted via `fast_pg_insert` from `database.py`:
```python
fast_pg_insert(trades, "trades")
fast_pg_insert(prices, "prices")
fast_pg_insert(internal, "internal")
```

- Why fail-first? Debugging messy data is a headache, so the general principle is no stupid ffils, default values etc. if we expect a value and it is not there then the run should fail 100%. 

## Best Practices — Data & Storage

Every run inserts ~40K rows across three tables and generates ~250MB of log files on disk. Treat storage as a constraint, not an afterthought.

### Table purposes

All subtables FK to `backtest_runs` via `backtest_id` with `ON DELETE CASCADE` — deleting a run automatically removes all its child rows.

| Table | Purpose | What goes here |
| :--- | :--- | :--- |
| **`backtest_runs`** | Parent table. One row per run. | Status, algo name, round, total PnL, per-product PnL (`jsonb`), dev name. Everything links back here. |
| **`prices`** | Everything the price chart needs. | Raw prices, volumes, order-book levels (bid/ask × 3 depth levels), mid price, PnL, **and all normalizers** (wallmid1, wallmid2, wallmidsma). If you add a new indicator/normalizer, it goes here as a new column. |
| **`trades`** | Trade data and classification. | Individual fills with buyer/seller, price, quantity, and the computed classification labels (`buyer_class`, `seller_class`), plus running `algo_position`. |
| **`internal`** | Data extracted from sandbox/lambda logs that cannot be obtained from the backtester output files. | Currently stores the **algo's own orders** (price + quantity per product per tick) because the backtester does not include placed orders in its output — only fills. Any future data that only exists inside the algo's runtime (signals, internal state snapshots) goes here via `[DATA]` logs. |

### DB column types
Use the smallest Postgres type that fits. The difference adds up fast at 40K rows/run:

| Type | Size | Use for |
| :--- | :--- | :--- |
| `smallint` | 2 bytes | Volumes, quantities, day, order-book levels — anything that fits in ±32K |
| `integer` | 4 bytes | Prices, timestamps |
| `real` | 4 bytes | Computed floats (wallmid, PnL) — round to 2dp before insert |
| `text` | variable | Only for backtest_id, product names, and similar identifiers |

Don't default to `integer` or `bigint` for everything. If adding a new column, pick the narrowest type and always set a `DEFAULT` (or use an Alembic migration) so existing rows aren't nuked.

### Algo: `json` not `jsonpickle`
IMC wiki tells use to use jsonpickle, piece of advice do NOT do that. Use `json.dumps` / `json.loads` for `traderData`, never `jsonpickle`. jsonpickle adds type metadata (e.g. `{"py/object": ...}`) that bloats the payload — wastes the 50K char competition limit and produces bigger `lambdaLog` entries in the stream log. 

### Log files on disk
Log files in `backend/logs/` are **not auto-deleted**. Two files (~250MB combined) are created per run and stick around forever. Clean them up manually or nuke your PC. The DB cleanup job only prunes Supabase rows — it does not touch local files since that seemed to wake stuff even worse. 

### General principles
- **Fail-first, no silent defaults.** If a value is missing, raise — don't ffill/default to 0 etc. Messy data is harder to debug than a failed run.
- **Round floats before insert.** 2 decimal places for prices/indicators. Full float64 precision wastes storage and makes CSV exports ugly. Only float4 used. 
- **Use indexes, not timestamps, for row operations.** Day -1 timestamps start at 1M which is just an offset — never rely on timestamp arithmetic for matching across dataframes. See current files whom all operate via the mask strat, aka creating an index mask that allows to operate via the index labels on the dfs via view not copy view.  
- **New normalizers/indicators → `prices` table.** New algo-internal runtime data → `internal` table via `[DATA]` logs. Don't mix these up.

## Dev - Frontend 
Just look for yourself is pretty self explanatory, just one **MAJOR** point, if you look at the files you will see some logic in the "fetches" that looks kinda weird but is just conditionally stiching day-1 and day-2 data together. This also explains our general approach to the day mgmt:
1. All days are treated as separate with a "day" column in the trades and prices df. 
2. BUT day -1 has timestamps 1 mill - 1.99 mil, note does not make any difference whatsoever, use proper indexes and NOT timestamps for location and matching, filtering etc when working with the dfs. 
3. The frontend "stitches" together the PnL and Position data automatically if "All" is selected 

**NOTE** Minor desing choice, NO data or similar loads in the frontend by default, the user must explicitly select all required options, this is in order to minimze unneccessary lag. For example we do not draw charts if props day, algo etc are not actrively set in the dropdown (no defaults).

Also one final easter egg! the route /leaderboard contains a leaderboard for current round! 
