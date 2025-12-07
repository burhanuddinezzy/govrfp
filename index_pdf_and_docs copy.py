import json 
import requests
from io import BytesIO
from elasticsearch import Elasticsearch, helpers

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='tika')

from tika import parser as tika_parser

ES_HOST = "http://localhost:9201"
INDEX_NAME = "sam_opportunities_v1"
INPUT = "sam_gov_output.json"

MAX_BYTES = 50 * 1024 * 1024 # 50 MB cutoff

es = Elasticsearch(ES_HOST)

from tika import parser as tika_parser
from io import BytesIO
import requests

MAX_BYTES = 50 * 1024 * 1024  # 50 MB cutoff

def fetch_and_extract(url, ui_link):
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()

        # Read content with max size limit
        data = BytesIO()
        written = 0
        for chunk in r.iter_content(chunk_size=8192):
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_BYTES:
                data.close()
                return "File skipped because too large"
            data.write(chunk)

        raw = data.getvalue()
        data.close()

        # Let Tika detect type automatically
        parsed = tika_parser.from_buffer(raw)
        if not parsed:
            print("Tika couldnt find it")
        else:
            print("TIka found stuff")
        content = parsed.get("content")

        if content:
            content = content.strip()
        else:
            content = "Unable to read content"
            print("Unable to read content. This attachment must be a scan or a picture")
            print(f"Attachment Link: {url}")

        return content

    except Exception as e:
        print(f"Error: {e}")
        return ""
    
with open(INPUT, "r") as f:
    data = json.load(f)

opps = data.get("opportunitiesData", [])
actions = []
noresourcelinks = 0

for item in opps:

    notice_id = item.get("noticeId")
    doc = {}

    fields_to_copy = [
        "noticeId", "title", "solicitationNumber", "fullParentPathName",
        "fullParentPathCode", "postedDate", "type", "baseType", "archiveType",
        "archiveDate", "responseDeadLine", "naicsCode", "classificationCode",
        "active", "pointOfContact", "description_text", "description_raw_api_url",
        "uiLink", "links", "resourceLinks"
    ]

    for k in fields_to_copy:
        if k in item:
            doc[k] = item[k]

    if not item.get("resourceLinks"):
        noresourcelinks += 1
    else:
        pdfs = []
        for url in item.get("resourceLinks", []) or []:
            text = fetch_and_extract(url, doc["uiLink"])

            # Only chunk if text is long; otherwise keep as one chunk
            chunk_size = 1_000_000
            if len(text) <= chunk_size:
                pdfs.append({
                    "pdf_url": url,
                    "pdf_title": url.split("/")[-1] or "",
                    "pdf_text": text
                })
            else:
                num_chunks = (len(text) // chunk_size) + 1
                for i in range(num_chunks):
                    start = i * chunk_size
                    end = start + chunk_size
                    chunk_text = text[start:end]
                    pdfs.append({
                        "pdf_url": url,
                        "pdf_title": f"{url.split('/')[-1]} ({i+1})",
                        "pdf_text": chunk_text
                    })

        doc["pdfs"] = pdfs

    actions.append({
        "_index": INDEX_NAME,
        "_id": notice_id,
        "_source": doc
    })

    if len(actions) >= 10:
        helpers.bulk(es,actions)
        print("Indexed batch of", len(actions))
        actions = []

print(f"No resource links found for {noresourcelinks} RFPs")

if actions:
    helpers.bulk(es, actions)
    print("Indexd final batch of", len(actions))

print("Done Indexing.")

es.delete_by_query(
    index="sam_opportunities_v1",
    body={
        "query": {
            "range": {
                "postedDate": {
                    "lt": "now-2M"  # 2 months before today
                }
            }
        }
    }
)

print("Removed documents older than 2 months.")




