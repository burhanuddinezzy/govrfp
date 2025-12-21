from elasticsearch import Elasticsearch
from start_elastic_search import start_elastic_search, close_elastic_search

es, started_container = start_elastic_search()

ES_HOST = "http://localhost:9201"
INDEX_NAME = "sam_opportunities_v1"

mapping = {
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "index.highlight.max_analyzed_offset": 1000000,  # <-- add this
    "analysis": {
      "analyzer": {
        "eng_with_stop": {
          "type": "standard",
          "stopwords": "_english_"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "noticeId": {"type": "keyword"},
      "title": {"type": "text", "analyzer": "eng_with_stop"},
      "solicitationNumber": {"type": "keyword"},
      "fullParentPathName": {"type": "text"},
      "fullParentPathCode": {"type": "keyword"},
      "postedDate": {"type": "date"},
      "type": {"type": "keyword"},
      "baseType": {"type": "keyword"},
      "archiveType": {"type": "keyword"},
      "archiveDate": {"type": "date"},
      "responseDeadLine": {"type": "date"},
      "naicsCode": {"type": "keyword"},
      "classificationCode": {"type": "keyword"},
      "active": {"type": "keyword"},
      "pointOfContact": {"type": "nested"},
      "description_text": {"type": "text", "analyzer": "eng_with_stop"},
      "description_raw_api_url": {"type": "keyword"},
      "uiLink": {"type": "keyword"},
      "links": {"type": "object"},
      "resourceLinks": {"type": "keyword"},
      "pdfs": {
        "type": "nested",
        "properties": {
          "pdf_url": {"type": "keyword"},
          "pdf_title": {"type": "text"},
          "pdf_text": {"type": "text", "analyzer": "eng_with_stop"}
        }
      },
    }
  }
}

es = Elasticsearch(ES_HOST)
if es.indices.exists(index=INDEX_NAME):
    print(f"Index {INDEX_NAME} exists, deleting...")
    es.indices.delete(index=INDEX_NAME)

es.indices.create(index=INDEX_NAME, body=mapping)
print("Index created:", INDEX_NAME)

close_elastic_search(es, started_container)