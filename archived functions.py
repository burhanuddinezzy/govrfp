
def select_clusters_based_on_aspect(embeddings, clusters_list, aspect_vectors, aspect_relevance_percentile):
    cluster_scores = []

    # Convert aspect_vectors dict to matrix (num_aspects, dim)
    aspect_matrix = np.vstack(list(aspect_vectors.values()))

    for cluster in clusters_list:
        if len(cluster) == 0:
            continue

        cluster_embeds = embeddings[cluster]  # shape: (num_passages, dim)
        cluster_centroid = np.mean(cluster_embeds, axis=0, keepdims=True)  # (1, dim)

        # Compute cosine similarity to all aspects
        sims = cosine_similarity(cluster_centroid, aspect_matrix).flatten()
        max_sim = sims.max()  # relevance to most similar aspect

        cluster_scores.append((cluster, max_sim))

    # Compute global threshold
    scores_array = np.array([s for _, s in cluster_scores])
    threshold = np.percentile(scores_array, aspect_relevance_percentile)

    # Select clusters above threshold
    selected_clusters = [cluster for cluster, score in cluster_scores if score >= threshold]

    if not selected_clusters:
        return "No relevant clusters found"

    return selected_clusters  # same structure as clusters_list

