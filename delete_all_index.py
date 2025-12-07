from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9201")

resp = es.delete_by_query(
    index="sam_opportunities_v1",
    body={
        "query": {
            "match_all": {}
        }
    }
)

print(f"Deleted {resp['deleted']} documents.")
