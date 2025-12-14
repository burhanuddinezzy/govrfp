# summarize the RFP, as in the scope of work, and pricing, ignore the legal stuff (no rich formatting, no break line):
import sys
import re
import numpy as np
import networkx as nx
import community as community_louvain
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from itertools import chain
from datetime import datetime
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

n = "03"
folder_path = f"summarizer/rfp_test_samples/sample_{n}"

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

aspect_vectors_path = "summarizer/aspects/aspect_vectors.npz"
data = np.load(aspect_vectors_path, allow_pickle=True)
names = data["names"]
vectors = data["vectors"]
aspect_vectors = {name: vectors[i] for i, name in enumerate(names)}
pricing_aspect_vector = np.load("summarizer/aspects/pricing_vector.npy")


def normalize_text(text):
    # Remove invalid UTF-8 bytes
    text = text.encode("utf-8", "ignore").decode("utf-8", "ignore")
    # Remove control chars and non-printable bytes (keep punctuation, $, %, etc.)
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", " ", text)
    # Lowercase
    text = text.lower()
    # Replace all newlines/tabs with spaces (flatten document)
    text = re.sub(r"[\n\r\t]+", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)        
    return text.strip()

MONEY_REGEX = re.compile(
    r"""
    (                       # start group
        \$\s*\d[\d,]*(\.\d+)?      # $3, $3,000, $3.25
        (?:\s*(k|K|m|M|million|billion))?   # allow $3k, $3 million
    )
    |
    (USD|usd)\s*\d[\d,]*(\.\d+)?   # USD 300, USD 300.50
    """,
    re.VERBOSE,
)

def split_passages(text, length=length):
    passages = []
    money_passages = []

    # cut text into chunks of fixed length
    for i in range(0, len(text), length):
        passage = text[i:i + length].strip()
        if not passage:
            continue

        if MONEY_REGEX.search(passage):
            money_passages.append(passage)
        else:
            passages.append(passage)

    return passages, money_passages

def build_similarity_graph_from_embeddings(embeddings, edge_percentile=edge_percentile): # The process of graph construction from embeddings
    n = len(embeddings)
    G = nx.Graph()
    G.add_nodes_from(range(n))
    
    sim_matrix = np.dot(embeddings, embeddings.T)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    sim_matrix /= (norms @ norms.T)
    np.fill_diagonal(sim_matrix, 0.0)
    
    triu = sim_matrix[np.triu_indices(n, k=1)]
    valid = triu[triu > 0]
    if valid.size == 0:
        return G
    
    threshold = np.percentile(valid, edge_percentile)
    for i in range(n):
        for j in range(i+1, n):
            if sim_matrix[i, j] >= threshold:
                G.add_edge(i, j, weight=float(sim_matrix[i, j]))
    return G

def cluster_graph(G): # The process of clustering the nodes (the embeddings) based on cosine similarity
    partition = community_louvain.best_partition(G, weight="weight")
    clusters = {}
    for node, cid in partition.items():
        clusters.setdefault(cid, []).append(node)
    
    clusters_list = list(clusters.values())

    # --- Print cluster sizes ---
    print(f"\n# of clusters:{len(clusters_list)} | Cluster size: {[len(c) for c in clusters_list]}")

    return clusters_list

def summarize_clusters(passages, embeddings, clusters, centrality_percentile=centrality_percentile):
    centrality_summary = []
    total_central_passages = 0

    for cluster in clusters:
        if len(cluster) == 0:
            continue

        cluster_passages = [passages[i] for i in cluster]
        cluster_embeds = embeddings[cluster]

        # --- Semantic centrality ---
        centroid = np.mean(cluster_embeds, axis=0, keepdims=True)
        sims = cosine_similarity(cluster_embeds, centroid).reshape(-1)
        thresh = np.percentile(sims, centrality_percentile)
        central_idxs = [i for i, s in enumerate(sims) if s >= thresh]

        total_central_passages += len(central_idxs)

        for idx in central_idxs:
            centrality_summary.append(cluster_passages[idx])
    
    return centrality_summary, total_central_passages

def summarize_pricing(passages, embeddings, pricing_percentile=pricing_percentile):
    pricing_summary = []
    total_central_passages = 0

    centroid = np.mean(embeddings, axis=0, keepdims=True)
    sims = cosine_similarity(embeddings, centroid).reshape(-1)
    thresh = np.percentile(sims, pricing_percentile)
    central_idxs = [i for i, s in enumerate(sims) if s >= thresh]

    total_central_passages += len(central_idxs)

    for idx in central_idxs:
        pricing_summary.append(passages[idx])
        
    return total_central_passages, pricing_summary

def select_clusters_based_on_aspect(embeddings,clusters_list,aspect_vectors,title_vector, description_vector, aspect_percentile,title_weight,description_weight,aspect_weight):
    cluster_scores = []

    # Stack centroid vectors (one per aspect)
    aspect_centroids = np.vstack(list(aspect_vectors.values()))  # (num_aspects, dim)

    for cluster in clusters_list:
        if len(cluster) == 0: continue

        cluster_embeds = embeddings[cluster]             # (n, dim)
        cluster_centroid = np.mean(cluster_embeds, axis=0, keepdims=True)  # (1, dim)

        # Similarity to title centroid
        sim_to_title = cosine_similarity(
            cluster_centroid,
            title_vector.reshape(1, -1)
        ).item()

        # Similarity to title centroid
        if description_vector is not None:
            sim_to_description = cosine_similarity(
                cluster_centroid,
                description_vector.reshape(1, -1)
            ).item()
        else:
            sim_to_description = 0

        # Similarity to each aspect centroid (take best match)
        sims_to_aspects = cosine_similarity(cluster_centroid, aspect_centroids).flatten()
        sim_to_aspect = sims_to_aspects.max()

        # Weighted score
        final_score = (title_weight * sim_to_title) + (description_weight * sim_to_description) + (aspect_weight * sim_to_aspect)

        cluster_scores.append((cluster, final_score))

    # Percentile threshold
    scores_array = np.array([s for _, s in cluster_scores])
    threshold = np.percentile(scores_array, aspect_percentile)

    selected_clusters = [cluster for cluster, score in cluster_scores if score >= threshold]

    if not selected_clusters:
        return "    No relevant clusters found"

    return selected_clusters

def summarize_rfp(text, model, title_vector, description_vector, title_weight, description_weight, aspect_weight):
    if not text:
        return "No Text Input"
    text = normalize_text(text)
    passages, money_passages = split_passages(text)
    money_text = "\n".join(money_passages)
    if not passages or not money_passages:
        return "No Passages found"
    embeddings = model.encode(passages, convert_to_numpy=True, show_progress_bar=False)
    pricing_embeddings = model.encode(money_passages, convert_to_numpy=True, show_progress_bar=False)
    G = build_similarity_graph_from_embeddings(embeddings)
    if G.number_of_edges() > 0: # Meaning no nodes (passages) were semantically similar, so no connections between nodes (edges) were formed
        clusters = cluster_graph(G)
    else: return "Number of edges = 0"
    if not clusters: return "No clusters found"
    
    relevant_clusters = select_clusters_based_on_aspect(embeddings,clusters,aspect_vectors,title_vector, description_vector, aspect_percentile,title_weight,description_weight,aspect_weight)

    summary, total_central_passages = summarize_clusters(passages, embeddings, relevant_clusters)
    summary_length = sum(len(c) for c in summary)
    print(f"\nText size = {len(text)} chars >>> {len(passages)} passages >>> retreived {total_central_passages} passages ({summary_length} chars)")

    pricing_total_central_passages, pricing_summary = summarize_pricing(money_passages, pricing_embeddings)
#output, total_chars
    flat_centrality = list(chain.from_iterable(summary)) if any(isinstance(i, list) for i in summary) else summary
    flat_pricing_centrality = list(chain.from_iterable(pricing_summary)) if any(isinstance(i, list) for i in pricing_summary) else pricing_summary

    centrality_text = "\n".join(flat_centrality) + "\n".join(flat_pricing_centrality)
    print(f"{len(money_passages)} money_passages({len(money_text)} chars) | Retreived {pricing_total_central_passages} passages({len("\n".join(flat_pricing_centrality))} chars)")

    return centrality_text

if __name__ == "__main__":
    title_file = f"{folder_path}/title.txt"
    summary_output = f"{folder_path}/summary.txt"
    sample_input = f"{folder_path}/sample_text.txt"

    with open(title_file, "r", encoding="utf-8") as r:
        title = r.read()
        
    title_vector = model.encode(title, normalize_embeddings=True)
    with open(sample_input, "r", encoding="utf-8") as r:
        text = r.read()

    log_file = "summarizer/log.txt"
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

    print(f"RUN {folder_path}| Timestamp: {datetime.now()}")
    print(f"Passage Length: {len} | Edge%={edge_percentile} | Centrality%={centrality_percentile} | Aspect%={aspect_percentile} | Pricing%={pricing_percentile} | TItle weight={title_weight} | Aspect weight={aspect_weight}")
    
    summary = summarize_rfp(text, model)    
    print(f"\nSummary length: {len(summary)} chars")    
    print("Comments:\n\n\n")

    with open (summary_output, "w") as f:
        f.write(summary)
    
    sys.stdout = sys.__stdout__
    log_f.close()
        
def summarize(full_text, title, description):
    title_vector = model.encode(title, normalize_embeddings=True)
    if description is not None:
        description_vector = model.encode(description, normalize_embeddings=True)
        title_weight=0.3
        description_weight = 4
        aspect_weight=0.3
    else:
        description_vector = None
        title_weight=0.5
        description_weight = 0
        aspect_weight=0.5

    print(f"RUN {folder_path}| Timestamp: {datetime.now()}")
    print(f"Passage Length: {len} | Edge%={edge_percentile} | Centrality%={centrality_percentile} | Aspect%={aspect_percentile} | Pricing%={pricing_percentile} | TItle weight={title_weight} | Description weight={description_weight} | Aspect weight={aspect_weight}")
    
    summary = summarize_rfp(full_text, model, title_vector, description_vector, title_weight, description_weight, aspect_weight)    
    print(f"\nSummary length: {len(summary)} chars")    
    print("Comments:\n\n\n")

    with open (summary_output, "w") as f:
        f.write(summary)
    
    sys.stdout = sys.__stdout__
    log_f.close()
