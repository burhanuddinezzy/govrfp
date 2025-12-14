# Purpose: When I run this: A CSV with RFP metadata + zip file of summary docs
# [Ive already ran the SAM API to fetch RFPs + Indexed them into ES]I run the ES search engine, and search for X keyword/ NAIC code/ Classification code (I dont need to run this because what ive indexed is incomplete as API doesnt pull description + links from links section (it only pulls links from ResourceLinks section))
# It returns a list of RFPs (json response)
# I manually fetch descriptions and any missing links, add them to the json response
# I run the summarizer, I will need to use Tika to pull text from pdf/urls, etc and feed into summarizer. read next
# Since I now am pulling description i would add description as an aspect if more than 200 chars. read next
# I would need to append texts from all the pdfs of the RFP, into one, so I have a single summary built from all the docs
# Output rfp metadata into csv and noticeID + summary into a docs, naming the docs by noticeID

# New Method
# I update the SAM API call to filter via SAM directly so the json resposne is pre-filtered for ICP.
# I manually fetch descriptions and any missing links, add them to the json response
# I run the summarizer, I will need to use Tika to pull text from pdf/urls, etc and feed into summarizer. read next
# Since I now am pulling description i would add description as an aspect if more than 200 chars. read next
# I would need to append texts from all the pdfs of the RFP, into one, so I have a single summary built from all the docs
# - output rfp metadata into csv and noticeID + summary into a docs, naming the docs by noticeID
from elastic_search.extraction_sources.sam_gov import fetch_rfps_from_sam_gov
from elastic_search.index_pdf_and_docs import index_rfps
from summarizer.summarizer import summarize
import numpy as np
from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
import csv
import os
import datetime
import sys
#OPEN LOG-----------------------
log_file = "log.txt"
log_f = open(log_file, "a", encoding="utf-8")
class Logger:
    def __init__(self, f):
        self.f = f
    def write(self, msg):
        self.f.write(msg)
        self.f.flush()
    def flush(self):
        self.f.flush()
sys.stdout = Logger(log_f)

#CONFIG-------------------------
length = 300 # for split passage
edge_percentile = 90 # to control minimum similarity required to connect nodes in graph
aspect_percentile = 90
title_weight=0.3
description_weight = 4
aspect_weight=0.3
# selects passages whose similarity to the cluster centroid is above the percentile value;
# np.percentile interpolates between values, so this may not correspond exactly to a strict top-X% by count
centrality_percentile = 80
pricing_percentile = 0
#-------------------------------
if __name__ == "__main__":
    step = input("step 1 or step 2 (enter 1 or 2)")

    if step == "1":
        naic_code = input("Provide naic_code or press enter")
        how_back = input("From today to when do you want to pull RFPs in days (just the number, so 7 for last 7 days)")

        fetch_rfps_from_sam_gov(naic_code, how_back) # Pull new RFPs from SAM.gov > retrieves sam_gov_output.json

        # I must manually update the json with descriptions and additional links (manually)

    if step == "2":
        index_rfps()

        ES_HOST = "http://localhost:9200"
        INDEX_NAME = "sam_opportunities_v1"

        es = Elasticsearch(ES_HOST)

        OUTPUT_FOLDER = "RFP_Summaries"
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        CSV_FILE = os.path.join(OUTPUT_FOLDER, "rfp_data.csv")

        metadata_fields = [
            "noticeId",                 # Unique identifier
            "title",                    # What the RFP is for
            "solicitationNumber",       # Official solicitation number
            "typeOfSetAsideDescription",# Set-aside info (if applicable)
            "naicsCode",                # NAICS for industry relevance
            "classificationCode",       # Classification code
            "fullParentPathName",       # Agency / office hierarchy
            "address",                  # Office / location info
            "responseDeadLine",         # Submission deadline
            "uiLink",                   # Link to the RFP
            "contact_fullName",         # Main contact(s)
            "contact_email",
            "contact_phone"
        ]

        print(f"Timestamp: {datetime.now()}")
        print(f"Passage Length: {len} | Edge%={edge_percentile} | Centrality%={centrality_percentile} | Aspect%={aspect_percentile} | Pricing%={pricing_percentile} | TItle weight={title_weight} | Aspect weight={aspect_weight}")

        # Prepare CSV
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=metadata_fields)
            writer.writeheader()

            # Use scan to iterate over all documents
            for doc in scan(es, index=INDEX_NAME, query={"query": {"match_all": {}}}):
                source = doc["_source"]

                # Collect base metadata for CSV
                csv_row = {k: source.get(k, "") for k in metadata_fields}

                # Handle multiple POCs in the same row
                point_of_contacts = source.get("pointOfContact", [])
                csv_row["contact_fullName"] = "\n".join([c.get("fullName", "") for c in point_of_contacts])
                csv_row["contact_email"] = "\n".join([c.get("email", "") for c in point_of_contacts])
                csv_row["contact_phone"] = "\n".join([c.get("phone", "") for c in point_of_contacts])

                # Combine officeAddress into single cell
                office_address = source.get("officeAddress", {})
                office_address_str = ", ".join(f"{k}: {v}" for k, v in office_address.items() if v)
                place_of_performance = source.get("placeOfPerformance", {})
                pop_str = ", ".join(f"{k}: {v}" for k, v in place_of_performance.items() if v)
                csv_row["address"] = f"Office:{office_address_str}\nPlace of performance:{pop_str}"

                # Write the row
                writer.writerow(csv_row)

                title = source.get("title", "")
                description = source.get("description", "")

                # Combine all PDFs
                pdfs = source.get("pdfs", [])

                text_parts = []
                for pdf in pdfs:
                    pdf_text = pdf.get("pdf_text", "")
                    if pdf_text:
                        text_parts.append(pdf_text)

                # Final combined text
                combined_text = " | ".join(text_parts)

                summary = summarize(combined_text, title, description)  

                # Save to file named by noticeId
                notice_id = source.get("noticeId", "unknown")
                print(f"\nSummary length for {notice_id}: {len(summary)} chars")  

                summary_file = os.path.join(OUTPUT_FOLDER, f"{notice_id}.txt")
                with open(summary_file, "w", encoding="utf-8") as f:
                    f.write(summary)