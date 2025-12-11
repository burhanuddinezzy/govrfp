from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9201")
count = es.count(index="sam_opportunities_v1")
print(count)
