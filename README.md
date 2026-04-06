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

1. main.py
2. core/parser.py (first half)
3. logger class 
4. existing frontend implementation

### Two ways to get data in
- **Run backtester** (`POST /run/`) — triggers the `prosperity4btx` binary with your algo file and a round ID. Results are streamed and auto-parsed.
- **Upload official log** (`POST /upload-json`) — upload a `.log` file downloaded from the Prosperity website (JSON format). Skips the backtester entirely, parses directly into the DB. Useful for analyzing competition results.

**Adding columns in Supabase?** Rows accumulate QUICKLY so generally two main points. A) delete data from scrap runs B) use alembic migs or default values in code when adding columns as to not nuke any previous runs.

### Automatic cleanup job (`backend/cleanup.py`)
Runs once on startup and then every 30 minutes in the background. It deletes from `backtest_runs` — child rows in `trades`, `prices`, and `internal` are removed automatically via `ON DELETE CASCADE`. Tunables are constants at the top of the file.

| Rule | What gets deleted |
| :--- | :--- |
| Failed runs | Any run with `status = 'FAILED'` |
| Zero PnL | Completed runs with `total_pnl = 0` or `NULL` |
| Stuck pending | `PENDING` runs older than 10 min (backtest never finished) |
| Previous-round bottom | For every round except the most recent, keeps only the top 10 by PnL |
| Global top-N | For runs older than 3 hours, keeps only the top 20 globally |

## Dev - Simulation and Logs 
- `main.py` -> runs the prosperity4btx backtester executable against the specified algo file in */backend/algos*. Two log files are produced per run, both written into */backend/logs/*:
  - **`{task_id}.log`** — written by the prosperity4btx binary itself (via `--out`). Contains the structured Activities log (prices CSV) and Trade History (trades JSON) that the parser reads.
  - **`{task_id}_stream.log`** — written by `main.py` by capturing every line of stdout from the subprocess. Contains the raw JSON lines printed by `logger.flush()` each tick (each with `sandboxLog` and `lambdaLog`), plus non-JSON status lines emitted by the backtester. This is what `inter.py` reads for internal data.

The Logger class (defined in each algo file — not `datamodel.py`) accumulates prints in memory and flushes a single JSON line to stdout at the end of each `run()` call. `main.py` picks that up and decides what to show in the terminal vs. write silently to the stream log. So to summarize the main idea is:

| Channel | Destination | Purpose | Format | Best Practice |
| :--- | :--- | :--- | :--- | :--- |
| **`self.logger.print()`** | `stream.log` + terminal | **Humans.** Real-time debugging and terminal milestones. | Plain Text / String | Use sparingly (e.g., every 1000 ticks) to avoid terminal spam. |
| **`self.logger.print("[DATA] ...")`** | `stream.log` only (silent) | **Post-run parsing.** Store structured data (orders, signals) per timestamp for offline analysis. | `[DATA] ` prefix + JSON string | **Use this for high-frequency data** (every tick). The `[DATA]` prefix is filtered from terminal output by `main.py` but is written to the stream log. **CRITICAL: this must be the ONLY `self.logger.print()` call in a given tick.** `inter.py` parses internal data by stripping `[DATA] ` from the entire `sandboxLog` and calling `json.loads()` on the result — if you mix in any plain debug print in the same tick, `sandboxLog` becomes `"debug msg\n{json}"` which is not valid JSON and crashes the parser. |
| **`traderData`** | Internal State / `lambdaLog` | **The Machine.** Persistent memory to pass variables to the next round. | JSON | **50k char limit in competition.** Only store what the bot needs to remember between ticks. Do NOT use this for logging. |
| **`print()`** | `sandboxLog` / raw stdout | **Terminal only, no log file.** Raw Python `print()` does appear in the terminal (via `sandboxLog` or the backtester's `--print` flag), but is **not** written to `stream.log` and cannot be post-parsed. | — | Avoid in production algo code. Use `self.logger.print()` so output is captured in the stream log. |

When writing your `run` method, follow this sequence to ensure the backtester captures everything correctly:

1. **Read Memory**: 
   `memory = jsonpickle.decode(state.traderData) if state.traderData else {}`

2. **Log for u (Stream)**: 
   `self.logger.print(f"Timestamp {state.timestamp}: Signal is {my_signal}")`

3. **Save for Algo (Memory)**: 
   `traderData = jsonpickle.encode(memory)`

4. **Output at EOF run() method**: 
   `self.logger.flush(state, result, conversions, traderData)`
   `return result, conversions, traderData`

Examples:

```python
def run(self, state: TradingState):
    # TERMINAL OUTPUT — shows in terminal during run, use sparingly
    if state.timestamp % 1000 == 0:
        self.logger.print(f"Timestamp {state.timestamp}: Position is {state.position.get('EMERALDS', 0)}")

    # SILENT DATA LOG — written to stream.log but NOT printed to terminal
    # Use this for every-tick structured data you want to parse afterwards
    self.logger.print(f"[DATA] {json.dumps({'ts': state.timestamp, 'orders': [[o.price, o.quantity] for o in my_orders]})}")
```

To parse `[DATA]` entries after a run, scan the `_stream.log` file for JSON lines, extract `sandboxLog`, and filter for lines starting with `[DATA]`.

The Logger class is **not** in `datamodel.py` — it is copy-pasted directly into each algo file. Check any existing algo (e.g. `algos/version1.py`) to see the full implementation.

## Dev - Computations
- `core/parser.py` handles both input modes. For the backtester it reads the `.log` file + `_stream.log`. For official uploads it reads the JSON directly. Either way it produces the same three DataFrames: `prices`, `trades`, `internal` — so everything downstream is identical.

The `internal` df is built from `[DATA]` log entries via `core/inter.py` and stored in the Supabase `internal` table.

The second half calls all the **pre computations** defined in */backend/core*. These computations modify the created
dataframe BEFORE inserting in the DB which is done at the end, this as it is a lot easier to NOT have to modify any
existing data in Supabase. This keeps the flow coherently tied only to pandas/np mgmt and database data is always good. **NOTE** here that all computations return a bool `True` **IF and and ONLY IF** the full computations complete perfectly. And only **IF** all computations return `True` do we persist a run in the db, otherwise it is discarded.

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

## Dev - Frontend 
Just look for yourself is pretty self explanatory, just one **MAJOR** point, if you look at the files you will see some logic in the "fetches" that looks kinda weird but is just conditionally stiching day-1 and day-2 data together. This also explains our general approach to the day mgmt:
1. All days are treated as separate with a "day" column in the trades and prices df. 
2. BUT day -1 has timestamps 1 mill - 1.99 mil, note does not make any difference whatsoever, use proper indexes and NOT timestamps for location and matching, filtering etc when working with the dfs. 
3. The frontend "stitches" together the PnL and Position data automatically if "All" is selected 

**NOTE** Minor desing choice, NO data or similar loads in the frontend by default, the user must explicitly select all required options, this is in order to minimze unneccessary lag. For example we do not draw charts if props day, algo etc are not actrively set in the dropdown (no defaults).
