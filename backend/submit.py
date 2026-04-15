from selenium import webdriver #type:ignore
from selenium.webdriver.chrome.options import Options #type:ignore
from selenium.webdriver.common.by import By #type:ignore
from selenium.webdriver import Keys, ActionChains #type:ignore
from selenium.webdriver.chrome.service import Service #type:ignore
import time, os, subprocess, sys
import httpx #type:ignore
from typing import List, Dict
from dotenv import load_dotenv #type:ignore

load_dotenv()

class ExpiredToken(Exception):
    """Exception for when our JWT expires"""
    def __init__(self):
        super().__init__()

class FailedToRun(Exception):
    """Exception for when algo fails"""
    def __init__(self, message):
        self.message = message
        super().__init__(message)

def download_file(url, filename):
    with httpx.stream("GET", url) as response:
        response.raise_for_status()
        with open(filename, "wb") as file:
            for chunk in response.iter_bytes():
                file.write(chunk)

def process_file(filepath: str, token: str):
    headers: Dict[str, str] = {'Authorization': f"Bearer {token}"}
    
    with open(filepath, "rb") as file:
        files = {'file': ("test-algo.py", file, "text/x-python")}
        sub_res = httpx.post("https://3dzqiahkw1.execute-api.eu-west-1.amazonaws.com/prod/submission/algo", headers=headers,
            files=files
        )
        if sub_res.status_code == 401:
            raise ExpiredToken()
        elif sub_res.status_code == 429:
            while True:
                time.sleep(30)
                sub_res = httpx.post("https://3dzqiahkw1.execute-api.eu-west-1.amazonaws.com/prod/submission/algo", headers=headers,
                    files=files
                )
                if sub_res.status_code == 200:
                    break
   
    ### get subid
    sub_id = sub_res.json()["data"]["id"]
    print("Successfully submitted algo: ", sub_id)
    time.sleep(4)

    while True:
        check_res = httpx.get("https://3dzqiahkw1.execute-api.eu-west-1.amazonaws.com/prod/submissions/algo/1?page=1&pageSize=1", headers=headers)  
        print(check_res)
        if check_res.status_code == 401:
            raise ExpiredToken()
        
        current_status = check_res.json()["data"]["items"][0]["status"]
        if current_status == "SIMULATING":
            print("Still simulating: ", sub_id)
            time.sleep(10)
            continue
        elif current_status == "FAILED":
            raise FailedToRun(f"Algo: {sub_id} failed to run on Prosperity's site")
        elif current_status == "FINISHED":
            ### get aws bucket url
            res = httpx.get(f"https://3dzqiahkw1.execute-api.eu-west-1.amazonaws.com/prod/submissions/algo/{sub_id}/zip", headers=headers)
            if res.status_code == 401:
                raise ExpiredToken()

            aws_bucket_url = res.json()["data"]["url"]
            ### download the file
            download_file(aws_bucket_url, f"{sub_id}.zip")
            ### unzip the file
            subprocess.run(["unzip", f"{sub_id}.zip", "*.log"])
            os.remove(f"./{sub_id}.zip")
            break

def main(browser_binary_location: str, email: str, password: str, files: List[str]):
    _options = Options()
    _options.binary_location: str = browser_binary_location
    _options.add_argument("--start-maximized")
    _options.add_argument("--guest")
    service = Service()

    with webdriver.Chrome(service=service, options=_options) as driver:
        driver.get("https://prosperity.imc.com/login")

        email_input = driver.find_element(by=By.NAME, value="email")
        email_input.send_keys(email)
        pass_input = driver.find_element(by=By.NAME, value="password")
        pass_input.send_keys(password)

        ActionChains(driver)\
            .send_keys(Keys.ENTER)\
            .perform()

        time.sleep(4)
        cookie_btn = driver.find_element(by=By.ID, value="onetrust-accept-btn-handler")
        cookie_btn.click()

        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(4)

        cookies = driver.get_cookies()
        access_arr = [token for token in cookies if 'CognitoIdentityServiceProvider' in token["name"] and '.idToken' in token["name"]]
        accessToken = access_arr[0].get("value")

        base_algo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../algos/"))

        for file in files:
            try:
                process_file(os.path.join(base_algo_path, file), accessToken)
            except ExpiredToken or FailedToRun as e:
                if type(e) == ExpiredToken:
                    new_cookies = driver.get_cookies()
                    new_access_arr = [token for token in new_cookies if 'CognitoIdentityServiceProvider' in token["name"] and '.idToken' in token["name"]]
                    new_token =  new_access_arr[0].get("value")
                    process_file(os.path.join(base_algo_path, file), new_token)
                else:
                    continue

if __name__ == "__main__":
    main(
        os.getenv("BROWSER_BINARY_LOCATION", ""), 
        os.getenv("IMC_EMAIL", ""), 
        os.getenv("IMC_PASS", ""),
        files=["test.py", "test.py"]
    )