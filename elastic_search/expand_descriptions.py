import json
import requests
from time import sleep

with open("config.json") as f:
    cfg = json.load(f)
    API_KEY = cfg.get("sam_gov", {}).get("api_key")

def update_sol_description():
    INPUT = "sam_gov_output.json"
    OUTPUT = "sam_expanded.json"

    with open(INPUT, "r") as f:
        data = json.load(f)

    opps = data.get("opportunitiesData")

    expanded = []
    for item in opps:
        out = dict(item)  # copy
        desc_url = item.get("description")
        params = {}
        params["api_key"] = API_KEY
        r = requests.get(desc_url, params=params, timeout=15)
        if r.status_code != 200:
            print(f"fetch error: {r.status_code}")
            desc_text = None
        
        desc_text = r.text

        out["description_text"] = desc_text
        out["description_raw_api_url"] = desc_url
        expanded.append(out)
        sleep(1)  # mild throttle

    with open(OUTPUT, "w") as f:
        json.dump({"opportunitiesData": expanded}, f, indent=2)
    print("Wrote", OUTPUT)

if __name__ == "__main__":
     update_sol_description()