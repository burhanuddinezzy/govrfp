# cd /home/bezzy/ALL_PROJECTS/elasticsearch-local
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='tika')

import csv
import json
from elasticsearch import Elasticsearch

ES_HOST = "http://localhost:9201"
INDEX_NAME = "sam_opportunities_v1"

es = Elasticsearch(ES_HOST)

def build_query(keywords, naics_code=None, classification_code=None, match_type="lenient", operator="or"):
    must_filters = []
    keyword_clauses = []

    # -----------------------------------------
    # STRUCTURED FIELD FILTERS (NAICS & Classification)
    # -----------------------------------------
    if naics_code:
        must_filters.append({
            "term": {"naicsCode.keyword": naics_code}
        })

    if classification_code:
        must_filters.append({
            "term": {"classificationCode.keyword": classification_code}
        })

    # -----------------------------------------
    # KEYWORD MATCHING
    # -----------------------------------------
    for kw in keywords:
        is_not = kw.lower().startswith("not ")
        term = kw[4:] if is_not else kw

        match_clause = {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": term,
                            "fields": ["title", "description_text"],
                            "type": "phrase" if match_type == "exact" else "best_fields",
                            "operator": "and" if operator == "and" else "or",
                            **({"fuzziness": "AUTO"} if match_type == "lenient" else {})
                        }
                    },
                    {
                        "nested": {
                            "path": "pdfs",
                            "query": {
                                "multi_match": {
                                    "query": term,
                                    "fields": ["pdfs.pdf_text", "pdfs.pdf_title"],
                                    "type": "phrase" if match_type == "exact" else "best_fields",
                                    "operator": "and" if operator == "and" else "or",
                                    **({"fuzziness": "AUTO"} if match_type == "lenient" else {})
                                }
                            },
                            "inner_hits": {
                                "_source": ["pdfs.pdf_title", "pdfs.pdf_url"],
                                "highlight": {"fields": {"pdfs.pdf_text": {}}}
                            }
                        }
                    }
                ]
            }
        }

        if is_not:
            # Negative keywords go in a top-level must_not
            must_filters.append({"bool": {"must_not": [match_clause]}})
        else:
            keyword_clauses.append(match_clause)

    # -----------------------------------------
    # COMBINE FILTERS AND KEYWORDS
    # -----------------------------------------
    bool_query = {
        "bool": {
            "must": must_filters
        }
    }

    if keyword_clauses:
        if operator == "and":
            # All keywords must match
            bool_query["bool"]["must"].extend(keyword_clauses)
        else:
            # At least one keyword should match
            bool_query["bool"]["should"] = keyword_clauses
            bool_query["bool"]["minimum_should_match"] = 1

    return bool_query

def search_rfps(keywords, match_type="lenient", operator="or", size=20, sort_by="relevance", naics_code=None, classification_code=None):
    query_body = {
    "query": build_query(keywords, naics_code, classification_code, match_type, operator),
    "highlight": {
        "require_field_match": False,
        "fields": {
            "title": {"fragment_size": 200, "number_of_fragments": 3},
            "description_text": {"fragment_size": 200, "number_of_fragments": 3},
            "pdfs.pdf_text": {"fragment_size": 200, "number_of_fragments": 5},
            "pdfs.pdf_title": {"fragment_size": 100, "number_of_fragments": 1}
        }
        }
    }

    response = es.search(index=INDEX_NAME, body=query_body, size=size)
    response_dict = dict(response)  # works in v8+ clients

    ES_DUMP = "es_response.json"
    with open(ES_DUMP, "w", encoding="utf-8") as w:
        json.dump(response_dict, w, indent=2)

    results = []

    for hit in response["hits"]["hits"]:
        source = hit["_source"]

        matched_keywords = set()
        fields_matched = set()
        pdfs_with_hits = []
        pdf_hit_counts = []
        total_occurrences = 0

        # Collect all snippet fragments with field title for consolidated snippet
        all_snippet_fragments = []

        # Top-level highlights
        highlights = {k: v for k, v in hit.get("highlight", {}).items() if not k.startswith("pdfs.")}
        for field_name, fragments in highlights.items():
            if fragments:
                fields_matched.add(field_name)
                matched_keywords.update([kw for kw in keywords if any(kw.lower() in frag.lower() for frag in fragments)])
                total_occurrences += len(fragments)
                for frag in fragments:
                    all_snippet_fragments.append(f"{field_name}: {frag}")

        # Nested PDF highlights via inner_hits
        pdf_hits = hit.get("inner_hits", {}).get("pdfs", {}).get("hits", {}).get("hits", [])
        for nested_hit in pdf_hits:
            pdf_source = nested_hit["_source"]
            pdf_title = pdf_source.get("pdf_title", "Unknown PDF")
            pdf_url = pdf_source.get("pdf_url", "")

            fragments = nested_hit.get("highlight", {}).get("pdfs.pdf_text", [])
            if fragments:
                fields_matched.add("pdfs.pdf_text")
                pdfs_with_hits.append(f"{pdf_title} ({pdf_url})")
                pdf_hit_counts.append(len(fragments))
                matched_keywords.update([kw for kw in keywords if any(kw.lower() in frag.lower() for frag in fragments)])
                total_occurrences += len(fragments)
                for frag in fragments:
                    all_snippet_fragments.append(f"PDF: {pdf_title} ({pdf_url}): {frag}")

        # Point of Contact
        poc_list = []
        for poc in source.get("pointOfContact", []):
            contact_info = " | ".join(filter(None, [
                poc.get("fullName"),
                poc.get("title"),
                poc.get("email"),
                poc.get("phone")
            ]))
            if contact_info:
                poc_list.append(contact_info)
        point_of_contact = " ; ".join(poc_list)

        results.append({
            "noticeId": source.get("noticeId"),
            "title": source.get("title"),
            "uiLink": source.get("uiLink"),
            "naicsCode": source.get("naicsCode"),
            "classificationCode": source.get("classificationCode"),
            "responseDeadLine": source.get("responseDeadLine", ""),
            "typeOfSetAsideDescription": source.get("typeOfSetAsideDescription", ""),
            "relevant_keywords": ", ".join(sorted(matched_keywords)),
            "total_keyword_hits": total_occurrences,
            "fields_matched": ", ".join(sorted(fields_matched)),
            "pdfs_with_hits": "; ".join(pdfs_with_hits),
            "pdf_hit_counts": "; ".join(map(str, pdf_hit_counts)),
            "pointOfContact": point_of_contact,
            "snippets": " ... ".join(all_snippet_fragments)
        })

    if sort_by == "occurrences":
        results.sort(key=lambda x: x["total_keyword_hits"], reverse=True)

    return results

def interactive_search():
    mode = input("Search mode: normal or custom? ").strip().lower()
    if mode not in ("normal", "custom"):
        mode = "normal"

    raw_input_str = input("Enter keywords or phrases: ").strip()

    if "," in raw_input_str:
        keywords = [kw.strip() for kw in raw_input_str.split(",")]
    else:
        keywords = [raw_input_str]

    # New structured filters
    naics_code = input("Filter by NAICS Code (leave blank for none): ").strip()
    naics_code = naics_code or None

    classification_code = input("Filter by Classification Code (leave blank for none): ").strip()
    classification_code = classification_code or None

    if mode == "normal":
        match_type = "lenient"

        if any(" " in kw for kw in keywords):
            operator = "and"
        else:
            operator = "or"

        size = 20
        sort_by = "relevance"

    else:
        match_type = input("Exact match? (y/n): ").strip().lower() == "y" and "exact" or "lenient"
        operator = input("Combine keywords with AND or OR? ").strip().lower() == "and" and "and" or "or"
        size = int(input("Number of results to fetch: ") or 20)
        sort_by = input("Sort by relevance or occurrences? ").strip().lower() == "occurrences" and "occurrences" or "relevance"

    results = search_rfps(
        keywords,
        match_type=match_type,
        operator=operator,
        size=size,
        sort_by=sort_by,
        naics_code=naics_code,
        classification_code=classification_code
    )

    for idx, r in enumerate(results):
        print(f"\nResult {idx+1}: \nTitle: {r['title']}\nNotice ID: ({r['noticeId']})")
        print(f"RFP Link: {r['uiLink']}")
        print(f"NAICS: {r['naicsCode']}")
        print(f"Classification: {r['classificationCode']}")
        print(f"Keywords matched: {r['relevant_keywords']}")
        print(f"Total keyword hits: {r['total_keyword_hits']}")
        print(f"Fields matched: {r['fields_matched']}")
        if r["pdfs_with_hits"]:
            print(f"PDFs with hits: {r['pdfs_with_hits']} ({r['pdf_hit_counts']})")
        if r["snippets"]:
            print(f"Snippet: ...{r['snippets']}...")

    save_csv = input("\nSave results to CSV? (y/n): ").strip().lower()
    if save_csv == "y":
        csv_file = "rfp_search_results.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "noticeId",
                "title",
                "uiLink",
                "naicsCode",
                "classificationCode",
                "responseDeadLine",
                "typeOfSetAsideDescription",
                "pointOfContact",
                "relevant_keywords",
                "total_keyword_hits",
                "fields_matched",
                "pdfs_with_hits",
                "pdf_hit_counts",
                "snippet"
            ])
            for r in results:
                writer.writerow([
                    r["noticeId"],
                    r["title"],
                    r["uiLink"],
                    r["naicsCode"],
                    r["classificationCode"],
                    r["responseDeadLine"],
                    r["typeOfSetAsideDescription"],
                    r["pointOfContact"],
                    r["relevant_keywords"],
                    r["total_keyword_hits"],
                    r["fields_matched"],
                    r["pdfs_with_hits"],
                    r["pdf_hit_counts"],
                    r["snippets"]
                ])

        print(f"Results saved to {csv_file}")

if __name__ == "__main__":
    interactive_search()
