# I need to apply retry logic as the api hangs often
import requests
from datetime import datetime, timedelta
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException


REMOTE_DEBUGGING_PORT = 9222
from captcha_handling import check_for_captcha


with open ("secret.json", "r") as r:
    config = json.load(r)
    api_key = config["sam_gov"]["api_key"]

def fetch_rfps_from_sam_gov(naic_code, how_back):
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=int(how_back))
    posted_from = start_date.strftime("%m/%d/%Y")
    posted_to = end_date.strftime("%m/%d/%Y")

    url = "https://api.sam.gov/opportunities/v2/search"

    params = {
        "api_key": api_key,
        "postedFrom": posted_from,
        "postedTo": posted_to,
        "ptype": "o",          # solicitation-type
        "limit": 1000,
        "offset": 0
    }

    if naic_code:
        params["ncode"] = naic_code

    #r = requests.get(url, params=params)
    r = requests.get(url, params = params, timeout=30)

    if r.status_code != 200:
        raise Exception(f"API request failed with status code {r.status_code}")

    data = r.json()

    print("\nConnecting to existing Chrome session...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{REMOTE_DEBUGGING_PORT}")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    print("Connected successfully!")       

    # Open a single new tab at the start
    driver.execute_script("window.open('about:blank', '_blank');")
    driver.switch_to.window(driver.window_handles[-1])

    opps = data.get("opportunitiesData", [])

    for item in opps:
        ui_link = item.get("uiLink")
        if not ui_link:
            continue

        driver.get(ui_link)

        try:
            check_for_captcha(driver, poll_interval=20)
        except RuntimeError:
            print("[INFO] Skipping URL due to captcha.")
            continue

        description_text = ""
        try:
            desc_el = driver.find_element(By.ID, "desc")
            description_text = desc_el.text.strip()
        except NoSuchElementException:
            print(f"[WARN] Description not found for {ui_link}")
        if description_text:
            description_text = " ".join(description_text.replace("\r", "\n").split())

        item["description"] = description_text

        existing_links = item.get("resourceLinks") or []
        if not isinstance(existing_links, list):
            existing_links = []

        try:
            links_container = driver.find_element(By.ID, "links-attachments")
            link_elements = links_container.find_elements(By.TAG_NAME, "a")

            for link in link_elements:
                href = link.get_attribute("href")
                if href and href not in existing_links:
                    existing_links.append(href)

        except NoSuchElementException:
            pass

        item["resourceLinks"] = existing_links

    with open ("sam_gov_output.json", "w") as f:
        json.dump(data, f, indent = 4)


if __name__ == "__main__":
    naic_code = input("Provide naic_code or press enter")
    how_back = input("From today to when do you want to pull RFPs in days (just the number, so 7 for last 7 days)")

    fetch_rfps_from_sam_gov(naic_code, how_back)
