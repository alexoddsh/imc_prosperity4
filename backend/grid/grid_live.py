import os
import sys
import csv
import time
import subprocess
import itertools
import yaml
from pathlib import Path
from argparse import ArgumentParser
from typing import List, Dict, Any, Callable, Generator
from io import BytesIO, TextIOWrapper, StringIO
from pycognito import Cognito
import httpx
from enum import IntEnum
import pandas as pd
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent #/backend
RESULT_DIR = BASE_DIR / "grid" / "results"
ALGO_PATH = BASE_DIR / "algos"
CONFIG_PATH = BASE_DIR / "grid" / "configs"

START_PARAMS = "# --- GRID PARAMS ---"
END_PARAMS = "# --- END GRID PARAMS ---"

AWS_USER_POOL_ID = "eu-west-1_wKiTmHXUE"
AWS_CLIENT_ID = "5kgp0jm69aeb91paqj1hnps838"

Yaml_OBJ = Dict[str, Any] | Dict
type ParamProduct = itertools.product

class YamlConfig(BaseModel):
    algo_file: str
    round: str
    year: str
    products: List[str]
    params: Dict[str, List]
    ###

class GlobalConfig:
    def setup(self, yaml_path: str):
        with open(yaml_path) as f:
            raw_yaml = yaml.safe_load(f)
        try:
            self.config = YamlConfig(**raw_yaml)
        except ValidationError as e:
            raise YamlConfigError(e)

class GridLiveException(Exception):
    """Base Exception"""
    def __init__(self, message):
        self.message = f"[GRID LIVE] {message}"
        super().__init__()

class YamlConfigError(GridLiveException):
    """Invalid yaml config"""
    def __init(self, err):
        self.message = f"Invalid Yaml config => {err}"
        super().__init__(self.message)

class ExpiredToken(GridLiveException):
    """Exception for JWT Expiry"""
    def __init__(self, ctx):
        self.message = f"JWT Expired at {time.strftime("%H:%M:%S", time.localtime())} (context={ctx})"
        super().__init__(self.message)

class FailedToRun(GridLiveException):
    """Exception for when an algo fails"""
    def __init__(self, sub_id):
        self.message = f"Algo run failed for submission: {sub_id}"
        super().__init__(self.message)

class MissingScraperConfigs(GridLiveException):
    def __init__(self, missing_vars: List[str]):
        self.message = f"Missing environment variable(s): <{missing_vars}>"
        super().__init__(self.message)

class UnexpectedAwsResponse(GridLiveException):
    def __init__(self, res: httpx.Response):
        self.message = f"Unexpected AWS response: {res}\n{res.headers}\n{res.text}"
        super().__init__(self.message)

class ReqMethod(IntEnum):
    GET = 0
    POST = 1

def destruct_template() -> tuple[List[str], List[str], List[str]]:
    algo_file_name = CONFIG.config.algo_file
    if not algo_file_name:
        raise Exception("Misconfigured .yaml file, does not have an algo")
    template_path = ALGO_PATH / algo_file_name

    with open(template_path, "r") as file:
        lines = [line for line in file.read().splitlines()]
        params_start = lines.index(START_PARAMS)
        params_end = lines.index(END_PARAMS)

        beforeParams = lines[:params_start]
        paramBlock = lines[params_start:params_end+1]
        afterParams = lines[params_end+1:]

        return beforeParams, paramBlock, afterParams

def manage_temp_algos(param_combinations: ParamProduct) -> Generator[tuple[BytesIO, int, tuple], None, None]:
    before_params, base_param_block, after_params = destruct_template()

    comb_iter: int = 0
    combs: List[tuple] = list(param_combinations)

    while comb_iter < len(combs):
        temp_param_block = []
        for index, param_line in enumerate(base_param_block[1:-1]):
            arr = param_line.split("=")
            temp_param_block.append(f"{arr[0]}= {combs[comb_iter][index]}")

        fileLines = [*before_params, *temp_param_block, *after_params]
        fileBytes = b''
        for line in fileLines:
            fileBytes += (line + '\n').encode('utf-8')

        buf = BytesIO(fileBytes)

        yield buf, comb_iter, combs[comb_iter]

        comb_iter += 1

def setup() -> ParamProduct:
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--config', help="name of yaml config file (in grid/configs)")
    args = arg_parser.parse_args()

    yaml_path = CONFIG_PATH / args.config
    CONFIG.setup(yaml_path=yaml_path)

    all_params = [tuple(vals) for vals in CONFIG.config.params.values()]
    all_combinations = itertools.product(*all_params)
    return all_combinations

def download_file(url, filename):
    with httpx.stream("GET", url) as response:
        response.raise_for_status()
        with open(filename, "wb") as file:
            for chunk in response.iter_bytes():
                file.write(chunk)

def tryAuthenticatedRequest(url: str, method: ReqMethod, headers: Dict, refresh_callback: Callable, **kwargs) -> httpx.Response:
    if method == ReqMethod.GET:
        res = httpx.get(url, headers=headers)
    else:
        res = httpx.post(url, headers=headers, **kwargs)

    if res.status_code == 401:
        print("AWS token expired, attempting 1 refresh")
        refresh_callback()

        if method == ReqMethod.GET:
            res = httpx.get(url, headers=headers, **kwargs)
        else:
            res = httpx.post(url, headers=headers, **kwargs)

        if res.status_code == 401:
            raise ExpiredToken(res.reason_phrase)
    
    elif res.status_code not in [200, 201]:
        raise UnexpectedAwsResponse(res)
    
    return res

def handle_log_file(file: TextIOWrapper) -> Dict:
    indexes = []
    file.seek(72) #junk data before this
    og_data: str = file.read(-1)

    for char_index, char in enumerate(og_data):
        if char == "\\" and og_data[char_index+1] == "n":
            indexes.append(char_index)
        elif char == "l" and og_data[char_index:char_index+4] == "logs":
            break

    price_csv_data = """"""
    price_csv_data += (og_data[:indexes[0]]) + '\n'

    leng = len(indexes) - 1
    for arrayIndex, indexVal in enumerate(indexes):
        if arrayIndex != leng:
            price_csv_data += (og_data[indexVal+2:indexes[arrayIndex+1]])
            if arrayIndex < leng-1:
                price_csv_data += '\n'

    df_prices = pd.read_csv(StringIO(price_csv_data), sep=";")

    round_pnls_by_product = {}
    for prod in df_prices["product"].unique():
        dfp = df_prices.query('product == @prod')
        round_pnls_by_product[f"pnl_{prod}"] = dfp["profit_and_loss"].iloc[-1]

    return round_pnls_by_product

def get_cognito_token(email: str, password: str) -> str:
    u = Cognito(
        user_pool_id=AWS_USER_POOL_ID,
        client_id=AWS_CLIENT_ID,
        username=email
    )
    u.authenticate(password=password)
    
    return str(u.id_token)

def main(email: str, password: str):    
    if not email or not password:
        raise MissingScraperConfigs([missing_var for missing_var in [email, password] if not missing_var])

    headers: Dict[str, str] = {}
    def refresh_auth():
        print("Refetching token AWS token")
        new_token = get_cognito_token(email, password)
        headers["Authorization"] = f"Bearer {new_token}"
    
    refresh_auth()

    algo_byte_generator = manage_temp_algos(setup())
    algo_template_name = CONFIG.config.algo_file.split(".")[0]
 
    with open(RESULT_DIR.joinpath(f"{algo_template_name}.csv") , "w", newline="") as csv_log_file:
        fieldnames = ['sub_id'] + [*CONFIG.config.params.keys()] + [f"pnl_{prod}" for prod in CONFIG.config.products]
        writer = csv.DictWriter(csv_log_file, fieldnames=fieldnames)
        writer.writeheader()

        for algoFile, iteration, combs in algo_byte_generator:
            with algoFile:
                files = {'file': (f"{algo_template_name}_{iteration}.py", algoFile, "text/x-python")}
                while True:
                    res = tryAuthenticatedRequest(
                        url="https://3dzqiahkw1.execute-api.eu-west-1.amazonaws.com/prod/submission/algo",
                        method=ReqMethod.POST,
                        headers=headers,
                        refresh_callback=get_cognito_token,
                        files=files
                    )
                    if res.status_code == 429:
                        print("Waiting for earlier submission to finish")
                        time.sleep(30)
                        continue
                    elif res.status_code == 201 or res.status_code == 200:
                        break

            sub_id = res.json()["data"]["id"]
            print("Successfully submitted algo: ", sub_id)
            time.sleep(4)

            while True:
                check_sub = tryAuthenticatedRequest(
                    url="https://3dzqiahkw1.execute-api.eu-west-1.amazonaws.com/prod/submissions/algo/2?page=1&pageSize=50",
                    method=ReqMethod.GET,
                    headers=headers,
                    refresh_callback=get_cognito_token,
                )

                current_status = check_sub.json()["data"]["items"][0]["status"]
                if current_status == "SIMULATING":
                    print("Still simulating: ", sub_id)
                    time.sleep(10)

                elif current_status == "ERROR_FINISHED":
                    crash_dict = {"sub_id": sub_id}
                    for field in fieldnames[1:]:
                        crash_dict[field] = 0
                    writer.writerow(crash_dict)
                    raise FailedToRun(f"Algo: {sub_id} failed to run on Prosperity's site")

                elif current_status == "FINISHED":
                    # get aws bucket url
                    bucket_url_res = tryAuthenticatedRequest(
                        url=f"https://3dzqiahkw1.execute-api.eu-west-1.amazonaws.com/prod/submissions/algo/{sub_id}/zip",
                        method=ReqMethod.GET,
                        headers=headers,
                        refresh_callback=get_cognito_token,
                    )
                    aws_bucket_url = bucket_url_res.json()["data"]["url"]
                    download_file(aws_bucket_url, f"{sub_id}.zip")

                    zip_proc = subprocess.run(["unzip", "-p", f"{sub_id}.zip", "*.log"], capture_output=True, check=True)
                    simulation_log = TextIOWrapper(BytesIO(zip_proc.stdout), encoding='utf-8')

                    with simulation_log as sim_log:
                        round_pnl_by_prod = handle_log_file(sim_log)
                    
                    combs_presented_by_header = list(zip(CONFIG.config.params.keys(), combs))
                    round_log = {"sub_id": sub_id}
                    for c in combs_presented_by_header:
                        round_log[c[0]] = c[1]
                    
                    final_round_log = round_log | round_pnl_by_prod
                    writer.writerow(final_round_log)
                    os.remove(f"./{sub_id}.zip")

                    break
                
                else:
                    raise UnexpectedAwsResponse(check_sub) 

if __name__ == "__main__":
    CONFIG = GlobalConfig()
    try:
        main(
            os.getenv("IMC_EMAIL", ""),
            os.getenv("IMC_PASS", "")
        )
    except GridLiveException as e:
        sys.exit(f"{e.message}")
    except KeyboardInterrupt:
        sys.exit("\nProcess aborted by user")
    except Exception as e:
        raise e