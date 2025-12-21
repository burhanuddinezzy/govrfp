from elastic_search.extraction_sources.sam_gov import fetch_rfps_from_sam_gov
from elastic_search.start_elastic_search import start_elastic_search, close_elastic_search
from elastic_search.index_pdf_and_docs import index_rfps
from summarizer.summarizer import summarize
import numpy as np
from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
import csv
import os
from datetime import datetime
import sys
import subprocess
import time

# --- Logger setup ---
log_file = "log.txt"
log_f = open(log_file, "a", encoding="utf-8")
INDEX_NAME = "sam_opportunities_v1"

class Logger:
    def __init__(self, f):
        self.f = f
    def write(self, msg):
        self.f.write(msg)
        self.f.flush()
    def flush(self):
        self.f.flush()

sys.stdout = Logger(log_f)

# --- Config ---
length = 300
edge_percentile = 90
aspect_percentile = 90
title_weight = 0.3
description_weight = 4
aspect_weight = 0.3
centrality_percentile = 80
pricing_percentile = 0

if __name__ == "__main__":
    sys.stdout = sys.__stdout__
    step = input("step 1 or step 2 or step 3(enter 1 or 2 or 3): ")
    sys.stdout = Logger(log_f)

    if step == "1":
        sys.stdout = sys.__stdout__
        naic_code = input("Provide naic_code or press enter: ")
        how_back = input("From today to when do you want to pull RFPs in days (number only): ")
        sys.stdout = Logger(log_f)

        fetch_rfps_from_sam_gov(naic_code, how_back)
        print("Step 1 complete: SAM.gov RFPs fetched. Manually update JSON with descriptions/links.")

    if step == "2":
        try:
            es, started_container = start_elastic_search()
            index_rfps(es)
            close_elastic_search(es, started_container)
        except Exception as e:
            print(f"Error during step 2: {e}")
            close_elastic_search(es, started_container)

    if step == "3":
        try:
            es, started_container = start_elastic_search()
            OUTPUT_FOLDER = "RFP_Summaries"
            os.makedirs(OUTPUT_FOLDER, exist_ok=True)

            CSV_FILE = os.path.join(OUTPUT_FOLDER, "rfp_data.csv")
            rfp_df = {}

            metadata_fields = [
                "noticeId", "title", "solicitationNumber", "typeOfSetAsideDescription",
                "naicsCode", "classificationCode", "fullParentPathName", "address",
                "responseDeadLine", "uiLink", "contact_fullName", "contact_email", "contact_phone"
            ]

            print(f"Timestamp: {datetime.now()}")
            print(f"Passage Length: {length} | Edge%={edge_percentile} | Centrality%={centrality_percentile} | "
                f"Aspect%={aspect_percentile} | Pricing%={pricing_percentile} | Title weight={title_weight} | Aspect weight={aspect_weight}")

            # --- Prepare CSV ---
            with open(CSV_FILE, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=metadata_fields)
                writer.writeheader()

                # --- Iterate over ES documents ---
                for doc in scan(es, index=INDEX_NAME, query={"query": {"match_all": {}}}):
                    source = doc["_source"]

                    # Base metadata
                    csv_row = {k: source.get(k, "") for k in metadata_fields}

                    # Multiple POCs
                    point_of_contacts = source.get("pointOfContact") or []
                    csv_row["contact_fullName"] = "\n".join([str(c.get("fullName") or "") for c in point_of_contacts])
                    csv_row["contact_email"] = "\n".join([str(c.get("email") or "") for c in point_of_contacts])
                    csv_row["contact_phone"] = "\n".join([str(c.get("phone") or "") for c in point_of_contacts])

                    # Combine addresses
                    office_address = source.get("officeAddress") or {}
                    office_address_str = ", ".join(f"{k}: {str(v)}" for k, v in office_address.items() if v is not None)

                    place_of_performance = source.get("placeOfPerformance") or {}
                    pop_str = ", ".join(f"{k}: {str(v)}" for k, v in place_of_performance.items() if v is not None)

                    csv_row["address"] = f"Office:{office_address_str}\nPlace of performance:{pop_str}"

                    # Write CSV row
                    writer.writerow(csv_row)

                    # Collect metadata for summarization
                    title = source.get("title", "")
                    description = source.get("description", "")
                    notice_id = source.get("noticeId", "unknown")

                    # Combine all PDFs into a single text
                    pdfs = source.get("pdfs", [])
                    combined_text = " | ".join([pdf.get("pdf_text", "") for pdf in pdfs if pdf.get("pdf_text")])

                    print(f"\nFull text length for {notice_id}: {len(combined_text)} chars")

                    rfp_df[notice_id] = {
                        "title": title,
                        "description": description
                    }

                    all_text_file = os.path.join(OUTPUT_FOLDER, f"{notice_id}.txt")
                    with open(all_text_file, "w", encoding="utf-8") as f:
                        f.write(combined_text)

            close_elastic_search(es, started_container)

            # --- Summarize text files ---
            for file in os.listdir(OUTPUT_FOLDER):
                if not file.endswith(".txt"):
                    continue

                notice_id = os.path.splitext(file)[0]
                file_path = os.path.join(OUTPUT_FOLDER, file)

                with open(file_path, "r", encoding="utf-8") as r:
                    text = r.read()

                meta = rfp_df.get(notice_id)
                if not meta:
                    continue

                summary = summarize(
                    text,
                    meta["title"],
                    meta["description"]
                )

                with open(file_path, "w", encoding="utf-8") as w:
                    w.write(summary)
        
        except Exception as e:
            print(f"Error during step 3: {e}")
            close_elastic_search(es, started_container)