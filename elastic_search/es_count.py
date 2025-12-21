import subprocess
import socket
import time
from elasticsearch import Elasticsearch
from elastic_search.start_elastic_search import start_elastic_search, close_elastic_search


es, started_container = start_elastic_search()

# Example: count documents
count = es.count(index="sam_opportunities_v1")
print(count)

close_elastic_search(es, started_container)