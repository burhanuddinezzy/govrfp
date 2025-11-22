# I need to apply retry logic as the api hangs often
# My datalake doesnt need to be infinitely big. Once a solicitation goes inactive, we can remove it. **No need to remove, leave for historical data, you dont need to store the content of the downloads, just need to store the download links, and then just the metadata of the solicitation
# ** update for above 2025.11.21, no need, keep everything. 
# Don't download documents, that should be client side.
# Need to vectorize the metadata of sols so users can do an AI search with normal search phrases
# Figure out how you can search through the attached docs of a sol for keywords and summarization.
import requests
from datetime import datetime, timedelta
import json

with open ("config.json", "r") as r:
    config = json.load(r)
    api_key = config["sam_gov"]["api_key"]

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