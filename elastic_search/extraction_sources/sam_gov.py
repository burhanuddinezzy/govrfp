# I need to apply retry logic as the api hangs often
import requests
from datetime import datetime, timedelta
import json

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
    r = requests.get(url, params = params)

    if r.status_code != 200:
        raise Exception(f"API request failed with status code {r.status_code}")

    data = r.json()

    with open ("sam_gov_output.json", "w") as f:
        json.dump(data, f, indent = 4)


if __name__ == "__main__":
    naic_code = input("Provide naic_code or press enter")
    how_back = input("From today to when do you want to pull RFPs in days (just the number, so 7 for last 7 days)")

    fetch_rfps_from_sam_gov(naic_code, how_back)
