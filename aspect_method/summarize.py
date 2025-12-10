import re
from sentence_transformers import SentenceTransformer
from itertools import chain
import sys
from datetime import datetime
import numpy as np

# CONFIG
min_len = 200 # for split passage
max_len = 300 # for split passage
aspect_vectors_path = "aspect_method/aspect_vectors.npz"
percentile = 90.0
top_k=None

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
    if not text: return "No Text Input"
    text = normalize_text(text)
    passages = split_passages(text)
    if not passages: return "No Passages found"
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    embeddings = model.encode(passages, convert_to_numpy=True, show_progress_bar=False)

    # Load aspect vectors
    data = np.load(aspect_vectors_path, allow_pickle=True)
    names = data["names"]
    vectors = data["vectors"]
    aspect_vectors = {name: vectors[i] for i, name in enumerate(names)}

    selected_indices = set()

    # Compare each aspect vector to all passage embeddings
    for aspect_name, aspect_vec in aspect_vectors.items():
        # Compute similarity (dot product, vectors assumed normalized)
        scores = np.dot(embeddings, aspect_vec)
        if len(scores) == 0:
            continue

        # Compute threshold based on percentile
        threshold = np.percentile(scores, percentile)
        candidate_indices = np.where(scores >= threshold)[0]

        # If top_k is set, take only the top_k highest-scoring passages
        if top_k is not None and len(candidate_indices) > top_k:
            # Sort candidate_indices by descending score and take top_k
            sorted_idx = candidate_indices[np.argsort(scores[candidate_indices])[::-1][:top_k]]
            selected_indices.update(sorted_idx)
        else:
            selected_indices.update(candidate_indices)


    if not selected_indices:
        return "No relevant passages found"

    # Build summary passages (keep original order)
    summary = [passages[i] for i in sorted(selected_indices)]
    # --- Flatten in case any cluster returns lists ---
    summary = list(chain.from_iterable(summary)) if any(isinstance(i, list) for i in summary) else summary
    # --- Convert to plain text ---
    summary = "\n\n".join(summary)
    summary = normalize_text(summary)

    return summary

if __name__ == "__main__":
    sample_input = "aspect_method/sample_text.txt"

    with open(sample_input, "r", encoding="utf-8") as r:
        text = r.read()

    log_file = "aspect_method/aspect_log.txt"
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
    print(f"\nParameters: min_len = {min_len} | max_len = {max_len}")

    summary = summarize_rfp(text)

    print(f"\nsummary length: {len(summary)}")

    with open ("aspect_method/summary.txt", "w") as f:
        f.write(summary)
    
    sys.stdout = sys.__stdout__
    log_f.close()

    print("Run completed. All output appended to aspect_log.txt")

        

