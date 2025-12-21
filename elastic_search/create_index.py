import subprocess
import socket
import time
from elasticsearch import Elasticsearch

host = "localhost"
port = 9201
container_name = "es_temp"
started_container = False  # Track if we started it

def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

def container_exists(name):
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name={name}", "-q"],
        stdout=subprocess.PIPE,
        text=True
    )
    return bool(result.stdout.strip())

def container_running(name):
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={name}", "-q"],
        stdout=subprocess.PIPE,
        text=True
    )
    return bool(result.stdout.strip())

def wait_for_es(host="localhost", port=9201, timeout=60):
    es = Elasticsearch(f"http://{host}:{port}")
    start_time = time.time()
    while True:
        try:
            if es.ping():
                return es
        except Exception:
            pass
        if time.time() - start_time > timeout:
            raise TimeoutError("Elasticsearch did not become ready in time")
        time.sleep(2)

# Handle Docker container
if not container_exists(container_name):
    print("Creating new Elasticsearch container...")
    subprocess.run(
        [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:9200",
            "--memory=1g",
            "--memory-swap=1g",
            "-e", "ES_JAVA_OPTS=-Xms512m -Xmx512m",
            "-e", "discovery.type=single-node",
            "-e", "xpack.security.enabled=false",
            "docker.elastic.co/elasticsearch/elasticsearch:8.12.0"
        ],
        check=True
    )
    started_container = True
elif not container_running(container_name):
    print("Starting existing container...")
    subprocess.run(["docker", "start", container_name], check=True)
    started_container = True

# Wait for ES to be ready
es = wait_for_es(host, port)
print("Elasticsearch is ready.")

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



es.close()

# Only stop/remove the container if this script started it
if started_container:
    subprocess.run(["docker", "stop", container_name])
    subprocess.run(["docker", "rm", container_name])