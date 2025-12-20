Project: govrfp

Purpose
The repository is a pipeline for collecting, indexing, searching, and summarizing U.S. federal RFP (Request For Proposal) / procurement opportunities (SAM.gov). The top-level `main.py` in the repository root is the orchestration script that runs the two primary phases: fetching RFP data (via SAM.gov) and processing/indexing + summarization.

High-level workflow
- Step 1 (data pull): Use the SAM.gov extraction code to fetch RFP metadata and produce a JSON file of RFPs (`sam_gov_output.json`). This is implemented in `elastic_search/extraction_sources/sam_gov.py` and invoked by `main.py` when you select step 1.
- Manual augmentation: the pipeline expects manual review/augmentation of the raw JSON to fill in missing `description` fields and to add any missing resource links (if required). The code documents indicate the SAM API may not include full descriptions or link targets in all fields.
- Step 2 (indexing + summarization): Run `main.py` with step 2. That calls `elastic_search/index_pdf_and_docs.index_rfps()` to extract PDF/text from resource links, index everything into an Elasticsearch index, then scans the index to create a CSV with RFP metadata and produce per-notice text files. Each per-notice text file is then summarized using the summarizer module and overwritten with the summary.

Files & folders (overview)
- `main.py` (root): the orchestrator. Prompts you for `step 1` or `step 2`:
  - If `1`: calls `fetch_rfps_from_sam_gov(naic_code, how_back)` (pulls new data and writes `sam_gov_output.json`).
  - If `2`: calls `index_rfps()` (see below), connects to ES at `http://localhost:9201` and the index `sam_opportunities_v1`, iterates over documents, writes `RFP_Summaries/rfp_data.csv` with metadata and creates a text file per `noticeId` that contains extracted PDF text (combined). It then calls `summarizer.summarize(text, title, description)` for each file and replaces the file contents with the generated summary.
- `elastic_search/`: Elasticsearch utilities and ingestion code
  - `create_index.py` / `delete_all_index.py` / `es_count.py`: helper utilities for managing the local ES index.
  - `extraction_sources/sam_gov.py`: code to call SAM.gov and build a JSON output of opportunities (used by step 1 in `main.py`).
  - `index_pdf_and_docs.py`: reads `sam_gov_output.json`, follows `resourceLinks` to download attachments, uses Apache Tika to extract text, attaches those texts to `pdfs` objects, and bulk-indexes documents into `sam_opportunities_v1`. The module also deletes old documents (older than ~1 month) after indexing. It imposes a size limit on downloaded files and splits very long extracted text into chunks.

- `summarizer/`: the summarization code
  - `summarizer.py`: the summarizer implementation and a callable `summarize(full_text, title, description)` function used by `main.py`.
    - Key algorithm steps:
      1. Normalize & clean text (strip non-printable chars, collapse whitespace).
      2. Split documents into fixed-length passages (default `length=300` characters) and also detect money/pricing passages via a `MONEY_REGEX`.
      3. Compute passage embeddings using `sentence-transformers/all-MiniLM-L6-v2`.
      4. Build a similarity graph where nodes are passages and edges join passages with cosine similarity above an `edge_percentile` threshold.
      5. Cluster the graph using the Louvain community detection algorithm (`python-louvain` package).
      6. Score clusters for relevance using a weighted combination of similarity to the title vector, description vector (if present), and precomputed aspect centroids loaded from `summarizer/aspects/aspect_vectors.npz` and `pricing_vector.npy`.
      7. For the clusters that score above the `aspect_percentile`, select passages near the cluster centroid (central passages) and assemble them into the final summary text. Pricing-related passages are optionally extracted separately.
    - Outputs the summary text (the public `summarize()` function prefixes the output with the original `Description:` followed by a separator and the extracted summary passages).

- `RFP_Summaries/`: output folder
  - `rfp_data.csv`: main CSV with selected metadata fields per RFP (written by `main.py` during step 2).
  - `*.txt` files named by `noticeId`: per-RFP combined text files (prior to summarization) and then overwritten with summary text by the pipeline.

- `sam_gov_output.json` (root and inside `elastic_search/extraction_sources/`): sample or actual SAM export. This is the canonical input to `index_pdf_and_docs.py`.

- `secret.json`: repository contains a `secret.json` - treat it as sensitive. The code may expect API keys or other secrets there; do not commit secrets to VCS.

Configurations & constants (important values found in code)
- Elasticsearch host: `http://localhost:9201` (used in `main.py`, `elastic_search/*`).
- Index name: `sam_opportunities_v1`.
- Summarizer defaults (found in `summarizer/summarizer.py` and mirrored in `main.py`):
  - `length = 300` (passage length)
  - `edge_percentile = 90` (graph edge threshold)
  - `aspect_percentile = 90` (cluster selection threshold)
  - `centrality_percentile = 80`
  - weighting: `title_weight`, `description_weight`, `aspect_weight` (tuned in code; description has higher weight when present)

How `main.py` orchestrates (detailed)
1. Logging: `main.py` opens `log.txt` and redirects `sys.stdout` to a file-based logger so print() ends up in the log (the code temporarily restores `sys.stdout` for interactive inputs).
2. User prompt: When executed interactively the script asks `step 1 or step 2`.
   - Step 1: The script asks for an optional `naic_code` and a number of days back to fetch. It calls `fetch_rfps_from_sam_gov(naic_code, how_back)` to pull new RFPs from SAM.gov and save them into `sam_gov_output.json`.
   - Step 2: Calls `index_rfps()` to perform the following:
       a. Read `sam_gov_output.json` (expected to contain `opportunitiesData`).
       b. For each opportunity, follow `resourceLinks` (if present), download each URL, extract text using Tika, attach a `pdfs` list with `pdf_url`, `pdf_title`, and `pdf_text` (large extracted text is chunked).
       c. Bulk index documents into Elasticsearch (`sam_opportunities_v1`) with the extracted `pdfs` as nested data.
       d. After indexing, `main.py` connects to ES, scans all docs and writes out a CSV with metadata fields (`noticeId, title, solicitationNumber, typeOfSetAsideDescription, naicsCode, classificationCode, fullParentPathName, address, responseDeadLine, uiLink, contact_fullName, contact_email, contact_phone`).
       e. For each document that has `pdfs.pdf_text`, combine the `pdf_text` values into a single text blob per `noticeId` (the code concatenates with ` | `), save it to `RFP_Summaries/<noticeId>.txt` and then call `summarizer.summarize(text, title, description)`. The returned summary replaces the file contents.

Search & interactive utilities
- `elastic_search/main.py` provides `search_rfps()` and an `interactive_search()` helper that:
  - Builds a flexible ES bool query combining keyword matching (top-level fields + nested `pdfs.pdf_text`) and structured filters (NAICS, classification code), supports negative keywords via prefix `not `, and returns highlighted snippets plus metadata.
  - Saves an ES JSON dump to `es_response.json` during searches and can save interactive results into `rfp_search_results.csv`.

Dependencies
- See `requirements.txt`. Key libraries used by the pipeline:
  - `sentence-transformers` (embedding model `all-MiniLM-L6-v2`)
  - `numpy`, `scikit-learn`
  - `networkx`, `python-louvain` (community detection)
  - `elasticsearch==8.12.0` (client)
  - `tika` (for text extraction from PDFs/attachments)
  - `requests`
  - `torch` (via extra index in `requirements.txt` for CPU wheels used by sentence-transformers)

Runtime / Quick start
1. Set up and run a local Elasticsearch instance accessible at `http://localhost:9201`.
2. Install Python packages (ideally in a venv). From project root:

   python3 -m pip install -r requirements.txt

3. Step 1: Fetch from SAM.gov (interactive):

   python3 main.py

   - Enter `1` when prompted, provide optional NAICS code and how many days back.
   - This writes `sam_gov_output.json` in the expected location (check `elastic_search/extraction_sources` for sample file).

4. (Manual) Edit `sam_gov_output.json` if descriptions or resource links are incomplete. The pipeline's summarizer benefits from having descriptive text available.

5. Step 2: Index, extract PDFs, create CSV, and summarize:

   python3 main.py

   - Enter `2` when prompted. The script will run `index_rfps()`, index into ES, create `RFP_Summaries/rfp_data.csv`, create/overwrite `RFP_Summaries/<noticeId>.txt` files and write summaries.

Notes, caveats, and recommendations
- Secrets & keys: `secret.json` may contain credentials—do not commit or expose real credentials. Load them securely if needed by the SAM extractor.
- Tika: the code uses `tika` to extract PDFs and attachments. Tika may require Java to be installed on the host. Large or scanned PDFs may not produce usable text (the code handles and logs those cases).
- Elasticsearch mapping: the code expects nested `pdfs` objects and uses an index named `sam_opportunities_v1`. If you re-create the index, ensure nested mappings exist for `pdfs` if you rely on inner_hits/highlights.
- Performance: embedding and clustering large documents can be CPU/memory intensive. The pipeline encodes passages with `sentence-transformers` which uses PyTorch; consider a machine with sufficient RAM and CPU, or GPU if available.
- Manual steps: the repo intentionally requires manual augmentation of SAM output to fill descriptions and links; automating that reliably would require additional extraction logic (e.g., following UI links and scraping descriptions).

Where to look next or extend
- Automate SAM augmentation: write a helper that fetches `uiLink` pages to attempt to auto-scrape missing descriptions and resources.
- Improve index mappings: add explicit ES mappings for text fields, analyzers, and nested `pdfs` mapping for more accurate scoring and highlighting.
- Batch & parallel extraction: `index_pdf_and_docs.fetch_and_extract` could be parallelized (careful with Tika and network limits).
- Add unit tests and CI to validate indexing and summarization behavior on sample inputs in `summarizer/rfp_test_samples`.

If you'd like, I can:
- Run tests or static checks (if provided).
- Add a short README in Markdown instead, or add a `README.md` variant.
- Create example commands or a tiny `run.sh` wrapper that performs step 1 and step 2 non-interactively.

End of README (plain text)
