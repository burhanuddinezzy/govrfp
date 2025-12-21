import subprocess
import socket
import time
from elasticsearch import Elasticsearch
from elastic_search.start_elastic_search import start_elastic_search, close_elastic_search

es, started_container = start_elastic_search()

resp = es.delete_by_query(
    index="sam_opportunities_v1",
    body={
        "query": {
            "match_all": {}
        }
    }
)

print(f"Deleted {resp['deleted']} documents.")

close_elastic_search(es, started_container)