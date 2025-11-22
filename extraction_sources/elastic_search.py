from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9201")

print(es.info())