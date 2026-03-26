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
from pathlib import Path
from core.parser import process_results # Import your parser

# Load credentials from your .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

app = FastAPI()

# --- CORS Setup ---
# Allows your Nuxt frontend (port 3000) to talk to this API (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Supabase Setup ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- Data Models ---
class RunRequest(BaseModel):
    algo_file: str
    round: str

# --- The Worker Engine ---
def execute_backtest(task_id: str, algo_file: str, round_id: str):
    try:
        # 1. Setup absolute paths
        base_path = os.path.dirname(os.path.abspath(__file__))
        algo_path = os.path.join(base_path, "algos", algo_file)
        log_dir = os.path.join(base_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{task_id}.log")

        # 2. THE FIX: Point directly to the verified binary path
        # This skips the "No module named" error entirely
        algo_dir = os.path.dirname(algo_path) 
        binary_exec = "/Users/alexoddsh/.local/share/virtualenvs/backend-dqIMmv-9/bin/prosperity4btx"
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{algo_dir}:{env.get('PYTHONPATH', '')}"

        cmd = [
            "/Users/alexoddsh/.local/share/virtualenvs/backend-dqIMmv-9/bin/prosperity4btx", 
            algo_path, 
            round_id, 
            "--out", log_path,
            "--print"
        ]

        print(f"\n--- [STARTING SIMULATION: {task_id}] ---")
        print(f"  [EXEC]: {binary_exec}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=algo_dir, 
            env=env
        )

        for line in process.stdout:
            print(f"  [PROSPERITY]: {line.strip()}")

        process.wait()

        if process.returncode == 0:
            print(f"--- [SUCCESS: {task_id}] ---")
            
            # This is what moves data from the .log file to the Dashboard/DB
            try:    
                print(f"  [PARSER]: Starting data extraction for {task_id}...")
                process_results(task_id, Path(log_path))
                print(f"  [PARSER]: Success. Dashboard should now be populated.")
                
            except Exception as e:
                print(f"  [PARSER ERROR]: {str(e)}")
                # If parsing fails, we still need to mark it so the UI stops spinning
                supabase.table("backtest_runs").update({"status": "FAILED"}).eq("id", task_id).execute()
        else:
            print(f"--- [FAILED: Exit Code {process.returncode}] ---")
            supabase.table("backtest_runs").update({"status": "FAILED"}).eq("id", task_id).execute()

    except Exception as e:
        print(f"--- [CRITICAL SYSTEM ERROR: {str(e)}] ---")
        supabase.table("backtest_runs").update({"status": "FAILED"}).eq("id", task_id).execute()

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