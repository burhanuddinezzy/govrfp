Project: FedScope Intelligence

Purpose
An intelligent pre-processing pipeline for U.S. federal procurement opportunities that solves a critical scaling problem: RFPs are too numerous and too long to review manually, yet too large for direct LLM summarization.

THE CORE PROBLEM:
Federal contractors face an impossible trade-off. SAM.gov publishes hundreds of procurement opportunities weekly, but each RFP spans 200-400 pages across multiple PDF attachments. You cannot:
  1. Read them all deeply (not enough time)
  2. Ignore them (might miss your perfect opportunity)
  3. Use LLMs directly (documents exceed token limits of GPT-4, Claude, etc.)

Even with 100k+ token context windows, a single 400-page RFP with technical specifications, past performance requirements, and evaluation criteria will exceed limits. You need human judgment to decide which opportunities deserve deep analysis, but you need automation to make that judgment scalable.

THE SOLUTION:
This pipeline performs intelligent semantic compression. It automatically fetches RFPs, extracts all PDF content, and generates targeted summaries that:
  - Preserve the most semantically relevant information (requirements, evaluation criteria, scope)
  - Reduce document length by 90%+ (400 pages → 40 pages of key content)
  - Fit comfortably within LLM token limits for follow-up summarization
  - Enable rapid go/no-go decisions without reading full documents

INTENDED USE CASE:
This is a filtering and prioritization tool, NOT a replacement for detailed RFP analysis. The workflow is:
  1. System generates pre-summaries for dozens of opportunities
  2. You review pre-summaries (5-10 minutes each) or feed them to an LLM for final summarization
  3. You identify the 3-5 opportunities worth pursuing
  4. You invest your time reading those full RFPs in depth
  5. You submit competitive proposals only where it makes sense

Result: Review 50+ opportunities per day instead of 5. Make informed decisions in minutes instead of hours. Read deeply only where it matters.

High-Level Workflow

The pipeline operates in three distinct phases:

Phase 1 - Data Acquisition (Step 1):
  - Query SAM.gov API for federal procurement opportunities
  - Filter by NAICS code and date range (configurable lookback period)
  - Export raw opportunity data to sam_gov_output.json
  - Manual augmentation step (optional): review and enhance descriptions or resource links

Phase 2 - Indexing & Extraction (Step 2):
  - Read sam_gov_output.json containing opportunity metadata
  - Download all PDF attachments from resourceLinks (handling documents up to 400+ pages)
  - Extract text content using Apache Tika (robust handling of scanned documents)
  - Bulk index documents into Elasticsearch (sam_opportunities_v1 index)
  - Store extracted PDF text as nested objects within each opportunity document
  - Apply automatic data retention (removes opportunities older than ~30 days)

Phase 3 - Intelligent Pre-Summarization (Step 3):
  - Scan Elasticsearch index and export metadata to RFP_Summaries/rfp_data.csv
  - Combine all PDF text per opportunity into single text files (often 100k+ characters)
  - Generate semantic summaries using graph-based clustering algorithm
  - Reduce document length by 85-95% while preserving critical information
  - Overwrite text files with compressed summaries ready for LLM consumption

The Semantic Compression Algorithm

The key innovation is treating summarization as a graph community detection problem rather than sequential extraction or simple keyword matching. This approach handles the unique challenges of procurement documents:
  - Critical information is scattered throughout (not concentrated at beginning/end)
  - Technical requirements appear in multiple contexts
  - Evaluation criteria may reference earlier sections
  - Boilerplate and redundant content must be filtered out

Algorithm Steps:

1. Text Preprocessing:
   - Normalize text (remove non-printable characters, collapse whitespace)
   - Detect pricing/monetary information using regex patterns
   - Preserve document structure while removing noise

2. Passage Segmentation:
   - Split documents into fixed-length passages (default: 300 characters)
   - Create overlapping context to preserve semantic continuity
   - Generate separate embeddings for each passage using sentence-transformers (all-MiniLM-L6-v2)

3. Graph Construction:
   - Build similarity graph where nodes = passages, edges = semantic relationships
   - Calculate cosine similarity between all passage pairs
   - Create edges only between passages with similarity above edge_percentile threshold (default: 90th percentile)
   - This creates a sparse graph connecting only strongly related content

4. Community Detection:
   - Apply Louvain algorithm to detect topical communities in the similarity graph
   - Each community represents a coherent theme (e.g., "technical requirements", "past performance", "evaluation criteria")
   - Communities naturally cluster related information scattered across the document

5. Relevance Scoring:
   - Score each community using weighted combination of:
     * Similarity to opportunity title embedding (title_weight = 0.3)
     * Similarity to description embedding (description_weight = 4.0) - dominant factor
     * Similarity to pre-trained procurement aspect centroids (aspect_weight = 0.3)
     * Presence of pricing/cost information (detected via regex)
   - Select only clusters scoring above aspect_percentile threshold (default: 90th percentile)
   - This filters out boilerplate, redundant sections, and low-relevance content

6. Summary Assembly:
   - Within high-scoring clusters, extract central passages (centrality_percentile = 80th)
   - Central passages are most representative of their cluster's theme
   - Combine with original opportunity description
   - Output compressed summary (typically 10-15% of original length)

WHY THIS APPROACH WORKS:
  - Preserves semantic coherence (communities keep related content together)
  - Filters redundancy (similar passages cluster together, only centroids extracted)
  - Prioritizes relevance (scoring based on title/description ensures focus on opportunity-specific content)
  - Handles scattered information (graph structure finds related content regardless of position)
  - Achieves massive compression (90%+ reduction) while retaining critical details

THE RESULT:
A 400-page RFP becomes a 40-page semantic summary containing:
  - Key technical requirements
  - Evaluation criteria
  - Performance requirements  
  - Pricing structures
  - Submission instructions
...all in a format that fits within LLM token limits for final summarization or Q&A.

Directory Structure & Key Files

Root Directory:
  main.py
    - Primary orchestrator script with three execution modes
    - Step 1: Fetch opportunities from SAM.gov API
    - Step 2: Index documents and extract PDF text into Elasticsearch
    - Step 3: Generate semantic pre-summaries and export metadata CSV
    - Manages Elasticsearch Docker container lifecycle automatically
    - Configures summarization parameters (passage length, percentile thresholds, scoring weights)
    - Logs all operations to log.txt for debugging and monitoring
    
  sam_gov_output.json
    - Output from Step 1 (SAM.gov data fetch)
    - Input for Step 2 (indexing and extraction)
    - Contains opportunitiesData array with RFP metadata and resourceLinks to PDF attachments
    - Can be manually augmented to improve summary quality
    
  secret.json
    - Configuration file for SAM.gov API credentials
    - CRITICAL: Do NOT commit to version control
    - Required for API access (may need to register at sam.gov)
    
  requirements.txt
    - Python dependencies with specific versions
    - Includes PyTorch CPU wheels from alternative index for lighter installation
    
  log.txt
    - Runtime log file (appended on each execution)
    - Contains progress updates, document lengths, extraction status, errors
    - Check this file if summaries are empty or quality is poor

elastic_search/:
  Elasticsearch management and data ingestion modules
  
  start_elastic_search.py
    - Manages Elasticsearch Docker container lifecycle
    - Automatically starts container if not running
    - Returns ES client connection and tracks whether container was started by script
    - Handles graceful shutdown in main.py
    - Used by both step 2 and step 3
  
  index_pdf_and_docs.py
    - Core indexing and extraction logic
    - Reads sam_gov_output.json and processes each opportunity
    - Downloads files from resourceLinks with size limits and timeout handling
    - Extracts text using Apache Tika server (handles PDF, DOCX, XLSX, etc.)
    - Chunks very long extracted text to stay within ES limits
    - Constructs nested pdfs objects with pdf_url, pdf_title, and pdf_text
    - Bulk indexes to sam_opportunities_v1 with automatic batching
    - Deletes opportunities older than retention threshold (~30 days)
    - Logs extraction failures and skipped documents
  
  extraction_sources/sam_gov.py
    - SAM.gov API client implementation
    - Function: fetch_rfps_from_sam_gov(naic_code, how_back)
    - Queries opportunities.sam.gov API endpoint with filters
    - Handles pagination and rate limiting
    - Writes formatted output to sam_gov_output.json
    - Used by main.py step 1
  
  create_index.py
    - Utility to create sam_opportunities_v1 index with proper mappings
    - Defines nested object mapping for pdfs array
    - Sets up analyzers for text fields
  
  delete_all_index.py
    - Utility to delete all documents from index (useful for testing)
  
  es_count.py
    - Utility to count documents in index and verify indexing success
  
  main.py (search interface)
    - Provides search_rfps() function for programmatic access
    - Supports interactive_search() with flexible query syntax
    - Combines keyword matching with structured filters (NAICS, classification codes)
    - Searches across both metadata fields and nested PDF text
    - Returns highlighted snippets showing match context
    - Exports results to rfp_search_results.csv
    - Saves raw ES response to es_response.json for debugging

summarizer/:
  NLP-based semantic compression engine
  
  summarizer.py
    - Main module exposing summarize(full_text, title, description) function
    - Implements complete graph-based clustering algorithm (detailed above)
    - Loads pre-trained aspect vectors from aspects/aspect_vectors.npz
    - Loads pricing detection vector from aspects/pricing_vector.npy
    - Uses sentence-transformers/all-MiniLM-L6-v2 for passage embeddings
    - Uses NetworkX for graph construction and analysis
    - Uses python-louvain for Louvain community detection
    - Uses scikit-learn for cosine similarity calculations
    - Returns formatted summary with description header and extracted high-relevance passages
    - Handles edge cases: empty documents, no high-scoring clusters, extraction failures
  
  aspects/
    - Contains pre-trained aspect centroids (aspect_vectors.npz)
    - Contains pricing vector (pricing_vector.npy)
    - These vectors represent common procurement topics and requirements
    - Used in relevance scoring to prioritize domain-specific content
    - Can be retrained on domain-specific corpora for specialized applications
  
  rfp_test_samples/
    - Sample RFP documents for testing and validation
    - Use these to verify summarization quality on known documents

RFP_Summaries/:
  Output directory created during step 3 (contains final deliverables)
  
  rfp_data.csv
    - Exported metadata for all indexed opportunities
    - Enables rapid filtering and sorting before reading summaries
    - Columns: noticeId, title, solicitationNumber, typeOfSetAsideDescription, 
              naicsCode, classificationCode, fullParentPathName, address,
              responseDeadLine, uiLink, contact_fullName, contact_email, contact_phone
    - Multiple contacts joined with newlines within cells
    - Address combines officeAddress and placeOfPerformance for complete location info
    - Use this CSV to identify opportunities worth detailed review
  
  <noticeId>.txt files
    - One file per opportunity (named by unique noticeId)
    - Initially contains combined PDF text (all attachments concatenated with " | " separator)
    - Overwritten with semantic pre-summary after clustering completes
    - Final files are 10-15% of original length but preserve critical information
    - Ready for LLM consumption or human review for go/no-go decisions

Configuration Parameters

Elasticsearch:
  Host: http://localhost:9201
  Index: sam_opportunities_v1
  Retention: ~30 days (older documents automatically deleted during indexing)
  Mapping: Nested objects for pdfs array to enable inner_hits and highlighting
  Connection: Managed automatically by start_elastic_search.py

Summarization (configured in main.py, lines 20-26):
  length = 300                    # Passage length in characters (affects granularity)
  edge_percentile = 90            # Graph edge similarity threshold (higher = sparser graph)
  aspect_percentile = 90          # Cluster relevance threshold (higher = more aggressive filtering)
  centrality_percentile = 80      # Passage centrality threshold for extraction within clusters
  pricing_percentile = 0          # Pricing passage threshold (0 = disabled by default)
  title_weight = 0.3              # Weight for title similarity in relevance scoring
  description_weight = 4.0        # Weight for description similarity (dominant factor - drives focus)
  aspect_weight = 0.3             # Weight for aspect vector similarity

Tuning Recommendations:
  - Lower aspect_percentile (e.g., 85) for longer summaries with more context
  - Raise aspect_percentile (e.g., 95) for ultra-compressed summaries (more aggressive)
  - Lower edge_percentile (e.g., 85) for denser graphs (more connections, less filtering)
  - Increase length (e.g., 400) for fewer, longer passages (faster but less granular)
  - Adjust description_weight up if descriptions are high quality, down if they're generic

File Processing:
  Max download size: Configurable in index_pdf_and_docs.py (default prevents memory issues)
  Text chunking: Applied to extracted text exceeding ES document size limits
  Supported formats: PDF, DOCX, XLSX, TXT, and any format supported by Apache Tika
  Timeout handling: Downloads that hang are terminated to prevent pipeline stalls

Dependencies

Core Libraries (see requirements.txt):
  - elasticsearch==8.12.0          # ES Python client with async support
  - sentence-transformers          # Text embeddings (downloads all-MiniLM-L6-v2 model ~90MB)
  - torch                          # PyTorch (CPU version via custom index for smaller install)
  - numpy                          # Numerical operations and vector math
  - scikit-learn                   # Cosine similarity, normalization, clustering utilities
  - networkx                       # Graph construction, analysis, and algorithms
  - python-louvain                 # Louvain community detection implementation
  - tika                           # PDF and document text extraction (auto-starts Tika server)
  - requests                       # HTTP client for SAM.gov API and PDF downloads

External Services:
  - Elasticsearch (Docker container, managed by start_elastic_search.py)
  - Apache Tika server (started automatically by tika-python library on first use)

System Requirements:
  - Python 3.8 or higher
  - Docker (for Elasticsearch container)
  - Java Runtime Environment (required by Apache Tika for text extraction)
  - 4GB+ RAM recommended (embedding and clustering large documents is memory-intensive)
  - 2GB+ disk space for Elasticsearch data and downloaded PDFs

Quick Start

1. Prerequisites:
   - Install Docker and ensure Docker daemon is running
   - Install Python 3.8 or higher (check: python3 --version)
   - Install Java Runtime Environment (check: java -version)
   - Verify Docker can run containers (check: docker ps)

2. Install Python dependencies:

   python3 -m pip install -r requirements.txt

   First run will download sentence-transformers model (~90MB) and start Tika server.

3. Configure SAM.gov API credentials (if using API):
   - Create or update secret.json with your API key
   - Register at https://open.gsa.gov/api/opportunities-api/ if needed
   - NEVER commit secret.json to version control

4. Run Step 1 (Data Acquisition):

   python3 main.py
   
   When prompted:
   - Enter "1" to run data acquisition
   - Optionally provide NAICS code (leave empty to fetch all industries)
   - Specify lookback period in days (e.g., "30" for last 30 days)
   
   Output: sam_gov_output.json containing opportunity metadata
   
   Check log.txt to verify successful API calls and data retrieval.

5. [Optional] Manual Enhancement:
   - Open sam_gov_output.json in a text editor
   - Review opportunities with empty or generic "description" fields
   - Fill in missing descriptions (improves semantic scoring dramatically)
   - Add missing resourceLinks if you have direct URLs to relevant documents
   - The summarizer's quality is directly tied to description completeness

6. Run Step 2 (Indexing & Extraction):

   python3 main.py
   
   When prompted:
   - Enter "2" to run indexing and extraction
   
   System will:
     * Start Elasticsearch Docker container (if not already running)
     * Read sam_gov_output.json
     * Download all PDF attachments from resourceLinks
     * Extract text from each PDF using Apache Tika
     * Index documents into sam_opportunities_v1 with nested pdfs objects
     * Delete opportunities older than retention period
     * Close ES connection and container (if started by script)
   
   This step can take 1-2 minutes per opportunity depending on PDF size.
   Check log.txt for extraction progress and any failed downloads.

7. Run Step 3 (Semantic Pre-Summarization):

   python3 main.py
   
   When prompted:
   - Enter "3" to run summarization
   
   System will:
     * Start Elasticsearch container if needed
     * Scan all indexed opportunities
     * Export metadata to RFP_Summaries/rfp_data.csv
     * Create combined text files (concatenating all PDF text per opportunity)
     * Display original text length for each opportunity
     * Generate semantic pre-summaries using graph clustering
     * Overwrite text files with compressed summaries
     * Display progress and statistics
   
   Summarization can take 30-60 seconds per opportunity for large documents.
   Check log.txt for detailed timing and cluster statistics.

8. Review Outputs:
   - Open RFP_Summaries/rfp_data.csv in Excel/spreadsheet software
   - Sort by responseDeadLine to prioritize urgent opportunities
   - Filter by naicsCode or keywords to find relevant opportunities
   - For interesting opportunities, read the corresponding <noticeId>.txt file
   - Feed summaries into ChatGPT/Claude for natural language Q&A or further compression
   - Decide which opportunities warrant reading the full original documents

Typical Workflow:
  Morning: Run steps 1-3 to process new opportunities from past 7 days
  Review: Scan rfp_data.csv (5 minutes) to identify 10 potentially relevant RFPs
  Triage: Read pre-summaries for those 10 opportunities (50 minutes total, 5 min each)
  Decision: Identify 2-3 RFPs worth pursuing based on summaries
  Deep Dive: Download and read full original documents only for those 2-3 RFPs
  Result: 2-3 high-quality proposals instead of 0-1 proposals from manual review

Search Interface (Optional Feature)

The elastic_search/main.py module provides an interactive search tool for ad-hoc queries:

   cd elastic_search
   python3 main.py

Features:
  - Keyword search across titles, descriptions, and full PDF text
  - Structured filters (NAICS codes, classification codes, date ranges)
  - Negative keywords with "not " prefix (e.g., "cybersecurity not training")
  - Boolean combinations (AND/OR logic)
  - Highlighted snippets showing match context
  - Export results to rfp_search_results.csv
  - Save raw ES response to es_response.json for debugging

Use this for targeted searches like:
  - "cloud migration" + NAICS 541512 (custom computer programming)
  - "artificial intelligence" + not "training" (exclude training contracts)
  - "cybersecurity" + classificationCode "D" (R&D contracts)

Technical Notes & Caveats

Elasticsearch:
  - Index mapping must support nested pdfs objects for proper highlighting and scoring
  - If you manually recreate the index, use create_index.py to ensure correct mappings
  - The scan operation in step 3 retrieves ALL documents; for indexes with 10,000+ opportunities this may take several minutes
  - Elasticsearch container uses ~1GB RAM; adjust Docker memory limits if needed

Apache Tika:
  - Automatically downloads Tika server JAR (~60MB) on first use
  - Requires Java Runtime Environment (JRE 8 or higher)
  - Scanned PDFs without OCR layer will produce empty or garbled text (logged as warnings)
  - Complex layouts (tables, multi-column) may have extraction issues
  - The code handles extraction failures gracefully and continues processing
  - Check log.txt for messages like "Failed to extract text from [URL]"

Summarization Performance:
  - Embedding and clustering is CPU/memory intensive
  - A 400-page document may take 1-2 minutes to summarize on typical hardware
  - sentence-transformers uses PyTorch; CPU-only by default
  - GPU acceleration would require different PyTorch installation (not included in requirements.txt)
  - First run downloads the embedding model (~90MB) automatically
  - RAM usage scales with document size (4GB minimum recommended, 8GB+ ideal)

Data Quality Factors:
  - SAM.gov API often returns incomplete or generic descriptions
  - Some opportunities lack resourceLinks entirely (nothing to extract)
  - Manual description enhancement in step 1 significantly improves summary quality
  - Empty or very short summaries usually indicate missing descriptions or failed PDF extraction
  - The algorithm weights description_weight=4.0 highly, so good descriptions drive better results

Token Limit Considerations:
  - Original RFPs: typically 50,000-200,000 tokens (way over any LLM limit)
  - Pre-summaries: typically 5,000-20,000 tokens (fits in GPT-4, Claude, etc.)
  - Further compression: feed pre-summary to LLM with prompt like "Summarize this RFP in 500 words"
  - Final result: 500-1,000 token summary suitable for rapid review

Security:
  - secret.json contains sensitive API credentials
  - Add secret.json to .gitignore immediately
  - Never commit credentials to version control or share logs containing keys
  - SAM.gov API may require registration and approval (check https://open.gsa.gov)

Logging:
  - All stdout redirected to log.txt (append mode)
  - Interactive prompts temporarily restore stdout for user input
  - Check log.txt for detailed progress, timing, and error messages
  - Useful for debugging failed extractions or low-quality summaries

Common Issues:
  - "Elasticsearch connection refused": Ensure Docker is running (docker ps)
  - "Tika server failed to start": Verify Java is installed (java -version)
  - "Empty summaries": Check if descriptions are populated in sam_gov_output.json
  - "Very short summaries": PDFs may have failed extraction (check log.txt)
  - "Low-quality summaries": Ensure description field is detailed and opportunity-specific
  - "Slow performance": Large documents require patience; consider lowering edge_percentile for faster processing

Extension Ideas & Future Work

1. Automated Description Enrichment:
   - Scrape uiLink pages to extract full opportunity descriptions from SAM.gov UI
   - Use GPT-4 or Claude to generate descriptions from PDF text when missing
   - Implement fallback description extraction from first few pages of primary PDF
   - This would eliminate the manual augmentation step

2. LLM Integration:
   - Add step 4 that feeds pre-summaries to OpenAI/Anthropic APIs automatically
   - Generate final 500-word summaries for each opportunity
   - Extract structured data (key dates, budget, requirements) using function calling
   - Create Q&A interface over opportunities

3. Enhanced Filtering:
   - Add ML-based relevance scoring based on past win/loss data
   - Implement company capability matching (compare RFP requirements to your past performance)
   - Build predictive models for win probability based on historical data
   - Create saved searches with email alerts for new matching opportunities

4. Performance Optimization:
   - Parallelize PDF downloads and extraction (careful with Tika server limits)
   - Batch embedding generation for faster processing
   - Use GPU for sentence-transformers if available (requires different torch installation)
   - Implement incremental indexing (only process new opportunities, skip already-indexed)
   - Cache embeddings to avoid recomputing on re-runs

5. Advanced Search Features:
   - Semantic search using opportunity embeddings (find similar RFPs)
   - Similarity-based recommendations ("opportunities like this one")
   - Dashboard with statistics, trends, and visualization
   - Saved search alerts and daily email digests
   - Browser extension to enhance SAM.gov UI with summaries

6. Quality Improvements:
   - Add unit tests for summarizer and indexing logic
   - Implement CI/CD pipeline with automated testing
   - Add data validation for SAM.gov API responses
   - Create evaluation metrics for summary quality (ROUGE, BERTScore)
   - A/B test different summarization parameters on known documents

7. User Interface:
   - Web dashboard for search, browse, and filtering
   - Email digest of new opportunities matching user preferences
   - Mobile app for on-the-go review
   - Browser extension for inline SAM.gov enhancement
   - REST API for programmatic access from other tools

8. Additional Data Sources:
   - Integrate state and local government procurement platforms
   - Cross-reference with past contract awards (USAspending.gov)
   - Add competitor tracking (who won similar contracts?)
   - Include industry news and trend analysis

9. Collaboration Features:
   - Multi-user support with shared opportunity lists
   - Team comments and ratings on opportunities
   - Workflow management (assign RFPs to team members)
   - Integration with CRM systems (Salesforce, HubSpot)

Where to Find Help

Documentation:
  - SAM.gov API docs: https://open.gsa.gov/api/opportunities-api/
  - Elasticsearch Python client: https://elasticsearch-py.readthedocs.io/
  - sentence-transformers: https://www.sbert.net/
  - NetworkX: https://networkx.org/documentation/stable/
  - Apache Tika: https://tika.apache.org/

Common Issues & Solutions:
  - "Elasticsearch not found": 
    * Check Docker is running: docker ps
    * Check start_elastic_search.py for container status
    * Verify port 9201 is not in use: netstat -an | grep 9201
  
  - "Tika server failed":
    * Verify Java is installed: java -version (need JRE 8+)
    * Check for firewall blocking Tika server startup
