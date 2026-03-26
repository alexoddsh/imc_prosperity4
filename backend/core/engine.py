import subprocess
import os
from pathlib import Path
from core.parser import process_results
from database import engine

def run_backtest_process(task_id: str, algo_name: str, round_id: str):
    base_dir = Path(__file__).parent.parent
    algo_path = base_dir / "algos" / f"{algo_name}.py"
    log_path = base_dir / "backtests" / f"{task_id}.log"
    
    log_path.parent.mkdir(exist_ok=True)

    with engine.begin() as conn:
        conn.execute(
            "INSERT INTO backtest_runs (id, algo_name, round_id, status) VALUES (:id, :a, :r, 'RUNNING')",
            {"id": task_id, "a": algo_name, "r": round_id}
        )

    cmd = ["prosperity4btx", str(algo_path), round_id, "--out", str(log_path)]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(base_dir))
    
    if result.returncode == 0:
        process_results(task_id, log_path)
    else:
        print(f"Backtest CLI Error: {result.stderr}")
        with engine.begin() as conn:
            conn.execute("UPDATE backtest_runs SET status = 'FAILED' WHERE id = :id", {"id": task_id})