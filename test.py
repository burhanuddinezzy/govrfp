import requests
import json

r = requests.get("https://sam.gov/workspace/contract/opp/d3332cbdaac941bb90bbf69fa61fbd7f/view")
print(r.status_code)
print(r.text)
