import platform
import uuid
import os
import asyncio
import logging
import json
import subprocess
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone
from core.models import LogFilter, SystemEnum, RunRequest
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, Form, File #type:ignore
from fastapi.middleware.cors import CORSMiddleware #type:ignore
from supabase import create_client, Client #type:ignore
from dotenv import load_dotenv #type:ignore
from core.parser import process_results
from cleanup import cleanup_loop, run_cleanup

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")
dev_name: str = os.environ.get("DEV_NAME", "unknown")
supabase: Client = create_client(url, key)

uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(LogFilter()) ## tell uvicorn to not stream INFO to stdcout


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_cleanup()  # run once on startup to clear any stale data
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def execute_backtest(task_id: str, algo_file: str, round_id: str, year: str):
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        algo_path = os.path.join(base_path, "algos", algo_file)
        log_dir = os.path.join(base_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{task_id}.log")

        algo_dir = os.path.dirname(algo_path) 
        
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{base_path}:{env.get('PYTHONPATH', '')}"

        if platform.system() == 'Darwin':
            if year == "4":
                data_input = "/Users/alexoddsh/prosperity/backend/backtester/resources-4"
            elif year == "3":
                data_input = "/Users/alexoddsh/prosperity/backend/backtester/resources-3"
        else:
            if year == "4":
                data_input = "/home/victor/notes/imc_prosperity4/backend/backtester/resources-4"
            elif year == "3":
                data_input = "/home/victor/notes/imc_prosperity4/backend/backtester/resources-3"

        cmd = [
            sys.executable, "-m", "backtester",
            algo_path, 
            round_id, 
            "--data", data_input, 
            "--out", log_path,
            "--print"
        ]

        print(f"\n  [STARTING SIMULATION: {task_id}]")
        
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
                if not clean:
                    continue

                if clean.startswith('{'):
                    try:
                        data = json.loads(clean)
                        sandbox_log = data.get("sandboxLog", "")
                        if sandbox_log:
                            for log_line in sandbox_log.splitlines():
                                if log_line.strip() and not log_line.strip().startswith("[DATA]"):
                                    print(f"  [ALGO]: {log_line.strip()}")
                                                                                                                   
                        lambda_log = data.get("lambdaLog", "")                    
                        if lambda_log.strip():                                                                                                             
                            for log_line in lambda_log.splitlines():
                                if log_line.strip().startswith("  [ALGO]:"):                                                                                                       
                                    print(log_line.strip())
                    except json.JSONDecodeError:
                        pass 
                else:
                    if "Successfully saved backtest results to" not in clean:
                        print(f"  [PROSPERITY]: {clean}")

                stream_f.write(clean + '\n')
                stream_f.flush()

        process.wait()

        def slog(msg):
            print(msg)
            with open(stream_log_path, 'a') as f:
                f.write(msg + '\n')

        if process.returncode == 0:
            try:
                slog(f"  [PARSER]: Starting data extraction for {task_id}...")
                if process_results(task_id, Path(log_path), Path(stream_log_path), SystemEnum.PROSPERITY4TBX) == 0:
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

@app.get("/")
async def root():
    return {"status": "online", "engine": "Prosperity BTX v4"}

@app.post("/run/")
async def run_backtest(req: RunRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())

    algo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "algos", req.algo_file)
    try:
        with open(algo_path, "r") as f:
            algo_code = f.read()
    except Exception:
        algo_code = None

    try:
        supabase.table("backtest_runs").insert({
            "id": task_id,
            "algo_name": req.algo_file,
            "round_id": req.round,
            "dev": dev_name,
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "algo_code": algo_code,
            "year": req.year
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")

    #background_tasks.add_task(execute_backtest, task_id, req.algo_file, req.round, req.year)
    await asyncio.to_thread(execute_backtest, task_id, req.algo_file, req.round, req.year)

    return {"task_id": task_id, "status": "Started"}

@app.post("/upload-json")
async def proccess_json(file: UploadFile = File(...), algo_file: str = Form(...), round: str = Form(...)):
    print("  [UPLOAD]: Saving log file")
    if not file.filename.endswith((".log")):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    task_id = str(uuid.uuid4())
    file_path = Path("logs") / f"{task_id}_{file.filename}"
    
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        supabase.table("backtest_runs").insert({
            "id": task_id,
            "algo_name": algo_file,
            "round_id": round,
            "dev": dev_name,
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "year": "4"
        }).execute()
        
        print("  [UPLOAD]: Attempting to parse log file")
        print("HELLLLO")     
        if process_results(task_id, file_path, None, SystemEnum.PROSPERITY) == 0:
            raise Exception("Parser returned 0")
        
        print("  [PARSER]: Success. Dash should now be populated")

        return {
            "task_id": task_id,
            "filename": file.filename,
            "status": "stored successfully",
            "path": str(file_path)
        }

    except Exception as e:
        supabase.table("backtest_runs").update({"status": "FAILED"}).eq("id", task_id).execute()
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        await file.close()
