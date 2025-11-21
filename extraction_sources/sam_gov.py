import requests
from datetime import datetime, timedelta
import json

with open ("config.json", "r") as r:
    config = json.load(r)
    api_key = config["sam_gov"]["api_key"]

# I need to apply retry logic as the api hangs often
today = datetime.today().date()
yesterday = today - timedelta(days=1)
posted_from = yesterday.strftime("%m/%d/%Y")
posted_to = today.strftime("%m/%d/%Y")

url = "https://api.sam.gov/opportunities/v2/search"
#url = f"https://sam.gov/api/prod/opps/v2/opportunities/fcc987f95a95446abb2ddf3a60dc20f2?api_key={api_key}&random=1763731134710"

params = {
    "api_key": api_key,
    "postedFrom": posted_from,
    "postedTo": posted_to,
    "ptype": "o",          # solicitation-type
    "limit": 2,
    "offset": 0
}

#r = requests.get(url, params=params)
r = requests.get(url, params = params)

if r.status_code != 200:
    raise Exception(f"API request failed with status code {r.status_code}")

data = r.json()

with open ("sam_gov_output.json", "w") as f:
    json.dump(data, f, indent = 4)


#d = requests.get("https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=ffa81523fcaa462eb594f1b507f785aa", params={"api_key": "SAM-2fee5606-66ca-4921-9991-555e65b11ae2"})
#print(d.json() if d.status_code == 200 else f"Error: {d.status_code}")