import os
from pathlib import Path
import uuid
import subprocess
from datetime import datetime, timezone
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from core.parser import process_results 

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

class RunRequest(BaseModel):
    algo_file: str
    round: str

def execute_backtest(task_id: str, algo_file: str, round_id: str):
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        algo_path = os.path.join(base_path, "algos", algo_file)
        log_dir = os.path.join(base_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{task_id}.log")

        #DO NOT CHANGE 
        algo_dir = os.path.dirname(algo_path) 
        binary_exec = os.environ.get("PROSPERITY4BTX_PATH")
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{algo_dir}:{env.get('PYTHONPATH', '')}"

        cmd = [
            "/Users/alexoddsh/.local/share/virtualenvs/backend-dqIMmv-9/bin/prosperity4btx", 
            algo_path, 
            round_id, 
            "--out", log_path,
        ]

        print(f"\n--- [STARTING SIMULATION: {task_id}] ---")
        print(f"  [EXEC]: {binary_exec}")

        stream_log_path = os.path.join(log_dir, f"{task_id}_stream.log")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=algo_dir,
            env=env
        )

        with open(stream_log_path, 'w') as stream_f:
            for line in process.stdout:
                clean = line.strip()
                print(f"  [PROSPERITY]: {clean}")
                stream_f.write(clean + '\n')
                stream_f.flush()

        process.wait()

        def slog(msg):
            print(msg)
            with open(stream_log_path, 'a') as f:
                f.write(msg + '\n')

        if process.returncode == 0:
            slog(f"--- [SUCCESS: {task_id}] ---")
            try:
                slog(f"  [PARSER]: Starting data extraction for {task_id}...")
                if process_results(task_id, Path(log_path)) == 0:
                    raise Exception("Parser returned 0")
                else:
                    slog("  [PARSER]: Success. Dash should now be populated")
            except Exception as e:
                slog(f"  [PARSER ERROR]: {str(e)}")
                supabase.table("backtest_runs").update({"status": "FAILED"}).eq("id", task_id).execute()
        else:
            slog(f"--- [FAILED: Exit Code {process.returncode}] ---")
            supabase.table("backtest_runs").update({"status": "FAILED"}).eq("id", task_id).execute()

    except Exception as e:
        msg = f"--- [CRITICAL SYSTEM ERROR: {str(e)}] ---"
        print(msg)
        try:
            with open(stream_log_path, 'a') as f:
                f.write(msg + '\n')
        except Exception:
            pass
        supabase.table("backtest_runs").update({"status": "FAILED"}).eq("id", task_id).execute()

@app.get("/logs/{task_id}")
async def get_run_logs(task_id: str):
    log_path = Path(os.path.dirname(os.path.abspath(__file__))) / "logs" / f"{task_id}_stream.log"
    if not log_path.exists():
        return {"lines": []}
    return {"lines": log_path.read_text().splitlines()}

@app.get("/")
async def root():
    return {"status": "online", "engine": "Prosperity BTX v4"}

@app.post("/run/")
async def run_backtest(req: RunRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())

    try:
        supabase.table("backtest_runs").insert({
            "id": task_id,
            "algo_name": req.algo_file,
            "round_id": req.round,
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")

    background_tasks.add_task(execute_backtest, task_id, req.algo_file, req.round)

    return {"task_id": task_id, "status": "Started"}