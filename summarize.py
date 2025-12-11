import sys
import re
import numpy as np
import networkx as nx
import community as community_louvain
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from itertools import chain
from datetime import datetime

aspect_vectors_path = "aspect_method/aspect_vectors.npz"
TITLE_TEXT = { "title": "EUR/Athens - Construction of half Basketball Court for US Embassy, Athens"}

# CONFIG
min_len = 200 # for split passage
max_len = 400 # for split passage
edge_percentile = 90 # to control minimum similarity required to connect nodes in graph
aspect_percentile = 90
tiny_cluster_size = 1
title_weight=0.7
aspect_weight=0.3

# selects passages whose similarity to the cluster centroid is above the percentile value;
# np.percentile interpolates between values, so this may not correspond exactly to a strict top-X% by count
centrality_percentile = 80
pricing_percentile = 30
# MMR isolation threshold: the minimum fraction of other passages that must be semantically dissimilar
# for a passage to be selected. Higher values make selection stricter, keeping only passages that are
# more isolated within the cluster.
mmr_isolation_threshold = 0.8

def normalize_text(text):
    text = text.lower()
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def split_passages(text, min_len=min_len, max_len=max_len):
    passages = re.split(r"\n\s*\n+", text)
    print(f"Initial split: {len(passages)} passages")

    merged = []
    money_passages = []
    buffer = ""

    for p in passages:
        if buffer:
            p = buffer + ". " + p
            buffer = ""

        if len(p) < min_len:
            buffer = p if not buffer else buffer + " " + p
        elif len(p) > max_len:
            # Split long passage into chunks of max_len
            start = 0
            while start < len(p):
                chunk = p[start:start + max_len].strip()
                if len(chunk) >= min_len:
                    if "$" in chunk:
                        money_passages.append(chunk)
                    else: 
                        merged.append(chunk)
                else:
                    buffer = chunk if not buffer else buffer + ". " + chunk
                start += max_len
        else:
            if "$" in p:
                money_passages.append(p)
            else:
                merged.append(p.strip())

    # If anything left in buffer, merge with last passage
    if buffer:
        if "$" in buffer:
            money_passages.append(buffer)
        else:
            merged.append(buffer.strip())

    print(f"Final split: {len(merged)} passages\n")
    return merged, money_passages

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
    print("Number of clusters:", len(clusters_list))
    for i, c in enumerate(clusters_list, start=1):
        print(f"Cluster {i} size: {len(c)}")

    return clusters_list

def summarize_clusters_semantic_centrality_mmr(passages, embeddings, clusters, tiny_cluster_size=tiny_cluster_size, centrality_percentile=centrality_percentile):
    centrality_summary = []
    mmr_summary = []
    tiny_cluster = 0
    total_central_passages = 0
    total_mmr_passages = 0

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

        # --- Tiny clusters → keep all passages ---
        if len(cluster_passages) <= tiny_cluster_size:
            tiny_cluster += 1
            centrality_summary.extend(cluster_passages)
            mmr_summary.extend(cluster_passages)
            continue

        for idx in central_idxs:
            centrality_summary.append(cluster_passages[idx])
        
    print(f"there were {tiny_cluster} tiny clusters found")
    print(f"\nThere are {total_central_passages} passages retrieved via centrality and {total_mmr_passages} passages retrieved via MMR")
    return centrality_summary

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
        
    print(f"\nThere are {total_central_passages} passages retrieved via centrality in pricing summary")
    return pricing_summary

def select_clusters_based_on_aspect(
        embeddings,
        clusters_list,
        aspect_vectors,   # dict: {aspect_name: centroid_vector}
        title_vector,     # shape: (dim,)
        aspect_percentile,
        title_weight,
        aspect_weight
        ):
    cluster_scores = []

    # Stack centroid vectors (one per aspect)
    aspect_centroids = np.vstack(list(aspect_vectors.values()))  # (num_aspects, dim)

    for cluster in clusters_list:
        if len(cluster) == 0:
            continue

        # Cluster centroid
        cluster_embeds = embeddings[cluster]             # (n, dim)
        cluster_centroid = np.mean(cluster_embeds, axis=0, keepdims=True)  # (1, dim)

        # Similarity to title centroid
        sim_to_title = cosine_similarity(
            cluster_centroid,
            title_vector.reshape(1, -1)
        ).item()

        # Similarity to each aspect centroid (take best match)
        sims_to_aspects = cosine_similarity(cluster_centroid, aspect_centroids).flatten()
        sim_to_aspect = sims_to_aspects.max()

        # Weighted score
        final_score = (title_weight * sim_to_title) + (aspect_weight * sim_to_aspect)

        cluster_scores.append((cluster, final_score))

    # Percentile threshold (NOT fixed percentage – this is correct percentile logic)
    scores_array = np.array([s for _, s in cluster_scores])
    threshold = np.percentile(scores_array, aspect_percentile)

    selected_clusters = [cluster for cluster, score in cluster_scores if score >= threshold]

    if not selected_clusters:
        return "No relevant clusters found"

    return selected_clusters

def summarize_rfp(text, model):
    if not text:
        return "No Text Input"

    text = normalize_text(text)

    passages, money_passages = split_passages(text)
    money_text = "\n".join(money_passages)
    print(f"There are {len(money_passages)} money_passages and {len(money_text)} characters")
    if not passages:
        return "No Passages found"
    if not money_passages:
        print("No money passages found")

    embeddings = model.encode(passages, convert_to_numpy=True, show_progress_bar=False)
    pricing_embeddings = model.encode(money_passages, convert_to_numpy=True, show_progress_bar=False)

    G = build_similarity_graph_from_embeddings(embeddings)

    if G.number_of_edges() > 0: # Meaning no nodes (passages) were semantically similar, so no connections between nodes (edges) were formed
        clusters = cluster_graph(G)
    else:
        return "Number of edges = 0"

    if not clusters:
        return "No clusters found"
    
    relevant_clusters = select_clusters_based_on_aspect(embeddings,clusters,aspect_vectors,title_vector,aspect_percentile,title_weight,aspect_weight)

    centrality_summary = summarize_clusters_semantic_centrality_mmr(passages, embeddings, relevant_clusters)
    pricing_summary = summarize_pricing(money_passages, pricing_embeddings)

    centrality_summary = [passages[i] for i in sorted([passages.index(p) for p in centrality_summary])]
    pricing_summary = [money_passages[i] for i in sorted([money_passages.index(p) for p in pricing_summary])]
    flat_centrality = list(chain.from_iterable(centrality_summary)) if any(isinstance(i, list) for i in centrality_summary) else centrality_summary
    flat_pricing_centrality = list(chain.from_iterable(pricing_summary)) if any(isinstance(i, list) for i in pricing_summary) else pricing_summary

    centrality_text = "\n".join(flat_centrality) + "\n".join(flat_pricing_centrality)
    print(f"There is {len("\n".join(flat_pricing_centrality))} chars retreived from pricing passages")

    return centrality_text

if __name__ == "__main__":
    data = np.load(aspect_vectors_path, allow_pickle=True)
    names = data["names"]
    vectors = data["vectors"]
    aspect_vectors = {name: vectors[i] for i, name in enumerate(names)}

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    title_text = list(TITLE_TEXT.values())
    title_vector = model.encode(title_text, normalize_embeddings=True)

    pricing_aspect_vector = np.load("aspect_method/pricing_vector.npy")

    sample_input = "sample_text.txt"

    with open(sample_input, "r", encoding="utf-8") as r:
        text = r.read()

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
    print("\n\n=== NEW RUN ===")
    print("Timestamp:", datetime.now())
    print("\nParameters:")
    print(f"min_len = {min_len} | max_len = {max_len} | tiny_cluster_size = {tiny_cluster_size}")
    print(f"\nedge_percentile = {edge_percentile}")
    print(f"centrality_percentile = {centrality_percentile}")

    centrality_summary = summarize_rfp(text, model)

    print(f"\nCentrality summary length: {len(centrality_summary)}")

    print("Writing to txt file")
    with open ("centrality_summary.txt", "w") as f:
        f.write(centrality_summary)
    
    sys.stdout = sys.__stdout__
    log_f.close()

    print("Run completed. All output appended to log.txt")

        

