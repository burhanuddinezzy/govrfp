import re
import numpy as np
import networkx as nx
import community as community_louvain
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from sklearn.metrics.pairwise import cosine_similarity
from itertools import chain

def normalize_text(text):
    text = text.lower()
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def split_passages(text, min_len=200, max_len=500):
    passages = re.split(r"\n\s*\n+", text)
    print(f"Initial split: {len(passages)} passages")

    merged = []
    buffer = ""

    for p in passages:
        if buffer:
            p = buffer + " " + p
            buffer = ""

        if len(p) < min_len:
            buffer = p if not buffer else buffer + " " + p
        elif len(p) > max_len:
            # Split long passage into chunks of max_len
            start = 0
            while start < len(p):
                chunk = p[start:start + max_len].strip()
                if len(chunk) >= min_len:
                    merged.append(chunk)
                else:
                    # Small leftover chunk → merge with previous
                    if merged:
                        merged[-1] += " " + chunk
                    else:
                        merged.append(chunk)
                start += max_len
        else:
            merged.append(p.strip())

    # If anything left in buffer, merge with last passage
    if buffer:
        if merged:
            merged[-1] += " " + buffer.strip()
        else:
            merged.append(buffer.strip())

    print(f"Final split: {len(merged)} passages")
    return merged

def build_similarity_graph_from_embeddings(embeddings, edge_percentile=75): # The process of graph construction from embeddings
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
    return list(clusters.values())

def mmr_distant_passages(cluster_embeds, similarity_threshold):
    n = cluster_embeds.shape[0]
    if n == 0:
        return []

    # Compute full pairwise similarity matrix
    sim_matrix = cosine_similarity(cluster_embeds)
    np.fill_diagonal(sim_matrix, 0.0)  # ignore self-similarity

    selected = []
    for i in range(n):
        # If this passage has no similarity >= threshold with any other, it's distant
        if not np.any(sim_matrix[i] >= similarity_threshold):
            selected.append(i)

    return selected

def summarize_clusters_semantic_centrality_mmr(passages, embeddings, clusters, tiny_cluster_size=1, centrality_percentile=90, mmr_similarity_threshold=0.1):
    centrality_summary = []
    mmr_summary = []
    tiny_cluster = 0

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

        # --- Tiny clusters → keep all passages ---
        if len(cluster_passages) <= tiny_cluster_size:
            tiny_cluster +1
            centrality_summary.extend(cluster_passages)
            mmr_summary.extend(cluster_passages)
            continue

        # --- Independent MMR on cluster ---
        mmr_idxs = mmr_distant_passages(cluster_embeds, similarity_threshold=mmr_similarity_threshold)

        # --- Combine outputs, remove duplicates ---
        #combined_idxs = list(dict.fromkeys(central_idxs + mmr_idxs))
        #for idx in combined_idxs:
        #    summary.append(cluster_passages[idx])

        for idx in central_idxs:
            centrality_summary.append(cluster_passages[idx])
        
        for idx in mmr_idxs:
            mmr_summary.append(cluster_passages[idx])

    print(f"there were {tiny_cluster} tiny clusters found")
    print(f"There are {len(central_idxs)} passages retrieved via centrality and {len(mmr_idxs)} passages retrieved via MMR")
    return centrality_summary, mmr_summary

def summarize_rfp(text, edge_percentile, tiny_cluster_size, min_passage_len):
    
    if not text:
        return "No Text Input"

    text = normalize_text(text)

    passages = split_passages(text, min_len=min_passage_len)
    if not passages:
        return "No Passages found"
    else:
        print(f"There are {len(passages)} passages")

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    embeddings = model.encode(passages, convert_to_numpy=True, show_progress_bar=False)

    G = build_similarity_graph_from_embeddings(embeddings, edge_percentile=edge_percentile)

    if G.number_of_edges() > 0: # Meaning no nodes (passages) were semantically similar, so no connections between nodes (edges) were formed
        clusters = cluster_graph(G)
    else:
        return "Number of edges = 0"

    if not clusters:
        return "No clusters found"

    centrality_summary, mmr_summary = summarize_clusters_semantic_centrality_mmr(
        passages,
        embeddings,
        clusters,
        tiny_cluster_size=tiny_cluster_size
    )

    # --- Flatten in case any cluster returns lists ---
    flat_centrality = list(chain.from_iterable(centrality_summary)) if any(isinstance(i, list) for i in centrality_summary) else centrality_summary
    flat_mmr = list(chain.from_iterable(mmr_summary)) if any(isinstance(i, list) for i in mmr_summary) else mmr_summary

    # --- Convert to plain text ---
    centrality_text = "\n\n".join(flat_centrality)
    mmr_text = "\n\n".join(flat_mmr)

    return centrality_text, mmr_text

def read_triple_quoted():
    print('Paste text between triple quotes. Start with """ and end with """')
    lines = []

    # Wait for opening delimiter
    while True:
        line = input().rstrip("\n")
        if line.strip() == '"""':
            break

    # Capture everything until closing delimiter
    while True:
        line = input()
        if line.strip() == '"""':
            break
        lines.append(line)

    return "\n".join(lines)

if __name__ == "__main__":
    text = read_triple_quoted()
    centrality_summary, mmr_summary = summarize_rfp(text, edge_percentile=75, tiny_cluster_size=1, min_passage_len=200)

    with open("centrality_summary.txt", "w", encoding="utf-8") as f:
        f.write(centrality_summary)

    with open("mmr_summary.txt", "w", encoding="utf-8") as f:
        f.write(mmr_summary)
        

