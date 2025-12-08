import re
import numpy as np
import networkx as nx
import community as community_louvain
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from sklearn.metrics.pairwise import cosine_similarity
from itertools import chain

# CONFIG
min_len = 200 # for split passage
max_len = 500 # for split passage
edge_percentile = 95 # to control minimum similarity required to connect nodes in graph
tiny_cluster_size = 1

# selects passages whose similarity to the cluster centroid is above the percentile value;
# np.percentile interpolates between values, so this may not correspond exactly to a strict top-X% by count
centrality_percentile = 95

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

    print(f"Final split: {len(merged)} passages\n")
    return merged

def summarize_rfp(text):
    if not text:
        return "No Text Input"

    text = normalize_text(text)

    passages = split_passages(text)
    if not passages:
        return "No Passages found"

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    embeddings = model.encode(passages, convert_to_numpy=True, show_progress_bar=False)
    # Reorder centrality_summary and mmr_summary based on original text order
    centrality_summary = [passages[i] for i in sorted([passages.index(p) for p in centrality_summary])]

    # --- Flatten in case any cluster returns lists ---
    flat_centrality = list(chain.from_iterable(centrality_summary)) if any(isinstance(i, list) for i in centrality_summary) else centrality_summary

    # --- Convert to plain text ---
    centrality_text = "\n\n".join(flat_centrality)

    centrality_text = normalize_text(centrality_text)

    return centrality_text

if __name__ == "__main__":
    import sys
    from datetime import datetime

    sample_input = "sample_text.txt"

    # --- Read input text ---
    with open(sample_input, "r", encoding="utf-8") as r:
        text = r.read()

    # --- Redirect stdout to log ---
    log_file = "aspect_log.txt"
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

    # --- Log header ---
    print("\n\n=== NEW RUN ===")
    print("Timestamp:", datetime.now())
    print("\nParameters:")
    print(f"min_len = {min_len} | max_len = {max_len} | tiny_cluster_size = {tiny_cluster_size}")

    print(f"\nedge_percentile = {edge_percentile}")
    print(f"centrality_percentile = {centrality_percentile}")
    print(f"mmr_similarity_threshold = {mmr_isolation_threshold}\n")

    # --- Run summarization ---
    centrality_summary = summarize_rfp(text)

    print(f"\nCentrality summary length: {len(centrality_summary)}")

    with open ("centrality_summary.txt", "w") as f:
        f.write(centrality_summary)
    
    # --- Restore stdout ---
    sys.stdout = sys.__stdout__
    log_f.close()

    print("Run completed. All output appended to log.txt")

        

