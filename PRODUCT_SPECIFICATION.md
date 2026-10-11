# Compass: Product Specification & Technical Status Report
**Project Title**: Agentic AI-Based Intelligent File Recommendation & Desktop Search System  
**Repository**: [Tejas-h-blitz/Compass](https://github.com/Tejas-h-blitz/Compass)  
**Status**: Working prototype (Phase 1 and 1.5 complete, Phase 2 in progress)  
**Date**: October 2026  
**License**: MIT  

---

## 1. Executive Summary

**Compass** is a high-performance, 100% local and privacy-first **Agentic Desktop Search and Intelligent File Recommendation System**. It bridges the gap between traditional lightweight keyword indexers (e.g., Windows Search, Everything) and modern neural semantic search engines. 

Running entirely offline without external API keys or cloud dependencies, Compass implements an **Agentic Perception–Deliberation–Action Loop**:
1. **Perception**: Scans scoped directory horizons across storage drives (C:, D:) with security guardrails (path blacklist plus best-effort secret redaction).
2. **Deliberation**: Dynamically routes user queries between low-millisecond (mean 3.22 ms, p95 4.61 ms from eval) keyword retrieval (SQLite FTS5 BM25) and dense vector semantic retrieval (ChromaDB + `all-MiniLM-L6-v2`), fusing scores and personalizing rankings via exponential recency decay curves ($S_{rec} = e^{-\lambda t}$).
3. **Action**: Serves proactive zero-query file recommendations, instant filtered search results via a Spotlight-style keyboard-driven desktop UI, and launches native files safely with strict executable containment.

---

## 2. Technology Stack & Architecture

```
                          ┌───────────────────────────────────────┐
                          │    Desktop UI (Spotlight / Raycast)   │
                          │   HTML5 / Vanilla CSS / ES6 / PyWebView│
                          └───────────────────▲───────────────────┘
                                              │ REST (Session Cookie)
                          ┌───────────────────▼───────────────────┐
                          │       FastAPI Application Server      │
                          │        (Host / Origin Shield)         │
                          └───────▲───────────────▲───────────────┘
                                  │               │
            ┌─────────────────────┴──────┐ ┌──────┴───────────────────────┐
            │   Dynamic Query Router     │ │ Proactive Recommendation Eng.│
            │  (backend/router/router.py)│ │(backend/search/recommend.py) │
            └───────┬─────────────┬──────┘ └──────────────▲───────────────┘
                    │             │                       │
      ┌─────────────▼──────┐ ┌────▼──────────────┐        │
      │ SQLite FTS5 Engine │ │ ChromaDB Vectors  │        │
      │ (BM25 Keyword)     │ │ (Cosine Similarity│        │
      └─────────────┬──────┘ └────┬──────────────┘        │
                    │             │                       │
                    └──────┬──────┘                       │
                           ▼                              │
            ┌────────────────────────────┐                │
            │   Personalization Engine   ├────────────────┘
            │(backend/search/personalize)│
            └──────────────▲─────────────┘
                           │
            ┌──────────────┴─────────────┐
            │ Multi-Horizon Scanner &    │
            │ Security Guardrails        │
            │(backend/scanner/scanner.py)│
            └────────────────────────────┘
```

### Core Subsystems

| Subsystem | Primary Technologies | File Location | Key Responsibility |
|:---|:---|:---|:---|
| **Relational & FTS Storage** | SQLite 3 + FTS5 Full-Text Engine | `backend/models/db.py` | Schema management, file metadata, hash tracking, access logging, and BM25 full-text indexing. |
| **Vector Embedding Storage** | ChromaDB (Local Persistent) | `backend/search/semantic_search.py` | Persistent vector index storage, collection management, and cosine distance nearest-neighbor queries. |
| **Embedding Model** | `sentence-transformers/all-MiniLM-L6-v2` | PyTorch / HuggingFace | Lightweight ~90MB local model executing fast CPU inference (384-dimensional dense embeddings). |
| **Ingestion & Scanner** | Python `os`, `pathlib`, `pypdf`, `python-docx` | `backend/scanner/scanner.py` | Recursive directory traversal, file format parsing (TXT, MD, PDF, DOCX, Code), mtime diff detection, pruning. |
| **Security Guardrail** | Regex sanitizer, path filters | `backend/scanner/scanner.py` | Path blacklist plus best-effort secret redaction: exclusion of private keys, `.env` files, system folders, Office lock files (`~$*`), and in-flight secret redaction. |
| **Query Classifier & Router** | Regex intent classifier, score blender | `backend/router/router.py` | Classifies queries into `keyword`, `semantic`, or `hybrid`; parallel execution; latency metric tracking. |
| **Personalization Engine** | Exponential recency decay algorithm | `backend/search/personalize.py` | Blends base search score with historical user interactions (frequency $S_{freq}$ and recency $S_{rec}$). |
| **Proactive Recommendations**| Multi-factor affinity scorer | `backend/search/recommend.py` | Generates intelligent zero-query file suggestions based on user access patterns and disk modification recency. |
| **Platform Launcher** | Python `os.startfile`, `subprocess` | `backend/platform/launcher.py` | Isolated OS launcher with safe Explorer reveal containment for script/executable extensions. |
| **API & Session Security** | FastAPI, HMAC tokens, Cookies | `backend/security/auth.py`, `backend/main.py` | Enforces one-time launch token redemption, session cookies, Host header DNS-rebinding shields, and Origin checks. |
| **Desktop Frontend** | Vanilla HTML5, CSS3, JavaScript (ES6) | `frontend/` (`index.html`, `index.css`, `app.js`) | Raycast/Spotlight dark-mode desktop interface with keyboard navigation (`↑`/`↓`/`↵`/`Esc`) and unauthorized session overlay. |

---

## 3. Mathematical & Algorithmic Specifications

### 3.1. Dynamic Query Routing
To prevent wasteful neural transformer inference on simple lookups:
- **Keyword Route**: Selected if query has $\le 2$ words or contains an explicit file extension (`.pdf`, `.docx`, `.py`, `.txt`, etc.).
- **Semantic Route**: Selected if query contains conceptual or natural language marker patterns (e.g., *"how to..."*, *"something about..."*, *"notes on..."*, *"overview of..."*).
- **Hybrid Route**: Selected for multi-token ambiguous queries, executing FTS5 and ChromaDB in parallel.

### 3.2. Hybrid Score Fusion
Hybrid search normalizes keyword score $S_{kw} \in [0, 1]$ and semantic cosine similarity $S_{sem} \in [0, 1]$, computing a weighted linear blend:
$$S_{hybrid} = w \cdot S_{kw} + (1 - w) \cdot S_{sem} \quad (\text{default } w = 0.5)$$

### 3.3. Frequency-Recency Personalization (Exponential Recency Decay)
User access events are tracked in `access_log`. For each document $f$:
$$S_{freq} = \frac{\text{AccessCount}(f)}{\max_{f'} \text{AccessCount}(f')}$$
$$S_{rec} = e^{-\lambda \cdot \Delta t}$$
Where $\Delta t$ is elapsed time in days since last user open, and:
$$\lambda = \frac{\ln(2)}{14.0} \approx 0.04951$$
This represents an exact 14.0-day half-life ($e^{-\lambda \cdot 14} = 0.5$).
The combined personalized score is:
$$S_{pers} = 0.5 \cdot S_{freq} + 0.5 \cdot S_{rec}$$
The final blended score returned to the user is:
$$S_{final} = 0.85 \cdot S_{base} + 0.15 \cdot S_{pers}$$
*(Under cold-start conditions with zero prior access logs, files receive $0.85 \cdot S_{base}$ to preserve discoverability).*

### 3.4. Proactive Zero-Query Recommendation Affinity
When search input is empty and the user activates "Suggestions", Compass ranks files using the actual scoring implementation in `backend/search/recommend.py`:

1. **For files with historical access logs**:
   $$\text{Score}(f) = 0.6 \cdot S_{rec} + 0.4 \cdot S_{freq}$$
   Where $S_{rec} = e^{-\lambda \cdot \Delta t}$ with $\lambda = \frac{\ln(2)}{14.0} \approx 0.04951$ (14.0-day half-life).
2. **For cold-start candidates (recently modified on disk, not yet accessed)**:
   $$\text{Score}(f) = 0.5 \cdot e^{-\lambda \cdot \Delta t_{disk}}$$
   Where $\Delta t_{disk}$ is elapsed time in days since last file modification on disk, using the exact same $\lambda \approx 0.04951$ (14.0-day half-life).

Files are tagged dynamically with status badges:
- `FAVORITE`: AccessCount $> 2$ and $S_{rec} > 0.6$
- `FREQUENT`: AccessCount $> 1$
- `RECENT`: Accessed recently (AccessCount $= 1$)
- `ACTIVE`: Modified recently on disk (cold-start)

---

## 4. Current Feature Implementation Status

### 4.1. Completed Features (Phase 1 & Phase 1.5)

| Feature | Implementation Details | Status |
|:---|:---|:---:|
| **Low-Millisecond Keyword Search** | SQLite FTS5 table with BM25 ranking, snippet generation, and exact token matching (mean 3.22 ms, p95 4.61 ms from eval). | **Implemented** |
| **Local Dense Vector Retrieval** | `all-MiniLM-L6-v2` generating 384-dim embeddings stored persistently in local ChromaDB. | **Implemented** |
| **Adaptive Query Routing** | Intent classifier routing between Keyword, Semantic, and Hybrid paths with latency tracking. | **Implemented** |
| **Personalization Engine** | Interaction logger, frequency normalization, exponential recency decay, and cold-start fallback. | **Implemented** |
| **Multi-Horizon Scoping** | Dynamic directory indexing across C: and D: drives with database tracking (`monitored_paths`). | **Implemented** |
| **Security Guardrails** | Path blacklist plus best-effort secret redaction: blacklist for sensitive directories (`.ssh`, `.aws`, `.git`, `AppData`, etc.), credentials, and private keys. | **Implemented** |
| **Secret Sanitizer** | In-flight regex redaction for AWS keys, GitHub tokens, OpenAI keys, and passwords before storage. | **Implemented** |
| **Office Lock File Immunity** | Automatic detection and exclusion of temporary Microsoft Office lock files (`~$*.docx`). | **Implemented** |
| **Proactive Zero-Query Engine** | Proactive recommendation endpoint ranking files by affinity without requiring any search query. | **Implemented** |
| **Modern Desktop UI (Spotlight)**| Obsidian Zinc dark theme, balanced sidebar, spacious 3–4 card layout, status badges. | **Implemented** |
| **Keyboard Ergonomics** | Full keyboard support: `↑`/`↓` arrow navigation, active focus highlights, `↵ Enter` to open, `Esc` to clear. | **Implemented** |
| **Native OS File Launching & Safe Reveal** | Strict allowlist: validates normalized path, disk existence, index membership, and monitored path containment. Dangerous executable/script extensions (.exe, .py, .bat, etc.) are blocked from execution and revealed in Explorer instead. | **Implemented** |
| **API Session Authentication & Host Shield** | Single-use launch code exchange, `HttpOnly` session cookie, DNS-rebinding `Host` header checks, and cross-origin `Origin` checks. | **Implemented** |
| **Automated Test Suite** | 5 core pipeline test suites (`test_step1.py` through `test_step5.py`) + 4 modular unit & security test suites (16 pytest tests passing). | **Implemented** |
| **Rigorous Evaluation Framework** | Ground-truth benchmarking script (`eval/run_eval.py`) measuring precision, recall, MRR, latency. | **Implemented** |

---

## 5. Security Model & Threat Boundaries

Compass implements local-first security hardening designed to treat the local API as untrusted by external processes and untrusted web pages:

1. **Session Authentication & Launch Code Lifecycle**:
   - At startup, `app.py` generates a single-use launch token via `secrets.token_urlsafe(32)`.
   - The launcher opens `http://127.0.0.1:8000/?launch=<code>`.
   - The backend validates the code using constant-time comparison (`hmac.compare_digest`), immediately consumes it so it cannot be reused, sets an `HttpOnly`, `SameSite=Strict` session cookie (`compass_session`), and redirects with HTTP 303 to clean `/`.
   - All `/api/*` endpoints require a valid session cookie. Unauthenticated requests return HTTP 401 Unauthorized.
   - If the frontend is loaded without an active session, an unauthorized overlay is presented ("Open Compass from the app window").
   - Dev/test bypass: `COMPASS_DISABLE_AUTH=1` (defaults to off; prints a prominent warning if enabled).
2. **Host Header Validation (DNS-Rebinding Defense)**:
   - HTTP middleware validates that the request `Host` header strictly matches `127.0.0.1:<port>` or `localhost:<port>`.
   - Requests with external host headers (e.g., attacker-controlled domains resolving to 127.0.0.1) are rejected with HTTP 400 Bad Request.
3. **Origin & Cross-Origin Request Defense**:
   - For state-changing operations (POST, PUT, DELETE), middleware verifies that any supplied `Origin` header matches the local host. Cross-origin requests initiated by malicious websites in user browsers are rejected with HTTP 403 Forbidden.
4. **File Launch Allowlist & Containment**:
   - `/api/log-access` normalizes client paths using `os.path.realpath` and `os.path.normcase`.
   - The path must physically exist on disk and must match an existing row in the `files` database index.
   - The path must be strictly contained within an active registered directory in `monitored_paths`. Requests outside monitored paths return HTTP 403 Forbidden and are not logged.
5. **Executable & Script Blocklist**:
   - The following file extensions are blocked from direct OS execution:  
     `.exe`, `.com`, `.bat`, `.cmd`, `.ps1`, `.psm1`, `.vbs`, `.vbe`, `.js`, `.jse`, `.wsf`, `.wsh`, `.hta`, `.msi`, `.msp`, `.scr`, `.pif`, `.lnk`, `.url`, `.reg`, `.jar`, `.cpl`, `.dll`, `.py`
   - When an indexed file matches a blocklisted extension, Compass executes `reveal_in_folder` (running `explorer.exe /select,<path>` via an argument list with `shell=False`) instead of launching it, and notifies the frontend via a toast.
6. **Known Limits & Threat Boundaries**:
   - **Best-Effort Secret Redaction**: In-flight regex sanitization redacts known API key patterns (AWS, OpenAI, Google, GitHub, RSA private keys, and standard password assignments). Bespoke secret formats or non-standard variable names may not be caught.
   - **Local Threat Model**: Hardening protects against malicious web pages (CSRF, DNS-rebinding, drive-by local API abuse) and external network callers. It does not defend against a local attacker who already possesses arbitrary code execution under the user's OS user account.

---

## 6. Empirical Benchmark & Performance Metrics

From the evaluation test runner (`eval/run_eval.py`):

> **Evaluation Caveat**: The evaluation set consists of **30 queries** (10 keyword, 10 semantic, 10 hybrid from `eval/test_queries.json`) evaluated across the test corpus. Note that this test suite is small and partly synthetic; semantic and hybrid retrieval achieved identical empirical scores on this specific query mix (P@1 = 0.967, R@3 = 1.000, MRR = 0.983).

| Retrieval Configuration | Precision@1 | Precision@3 | Recall@3 | MRR | Mean Latency | p95 Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Keyword-Only (FTS5)** | 0.467 | 0.156 | 0.467 | 0.467 | **3.22 ms** | **4.61 ms** |
| **Semantic-Only (ChromaDB)** | **0.967** | **0.333** | **1.000** | **0.983** | 18.10 ms | 22.11 ms |
| **Hybrid-Only (Fused)** | **0.967** | **0.333** | **1.000** | **0.983** | 19.30 ms | 22.47 ms |
| **Dynamic Router (Compass)** | **0.967** | **0.333** | **1.000** | **0.983** | **12.76 ms** | **19.97 ms** |

### Key Benchmark Findings:
1. **Accuracy Parity**: The Dynamic Router matches the semantic accuracy of ChromaDB (Precision@1 = **0.967**, Recall@3 = **1.000**, MRR = **0.983**).
2. **Latency Reduction**: The Router reduces average retrieval latency from 19.30 ms to **12.76 ms** (about **34% lower mean latency on this query mix**), routing simple token and file extension lookups to SQLite FTS5 in **3.22 ms**.

---

## 7. REST API Contract Reference

The backend exposes the following REST API endpoints at `http://127.0.0.1:8000`:

> **Authentication Notice**: All `/api/*` endpoints require an active session cookie (`compass_session`). Requests without a valid session return **401 Unauthorized**. Requests targeting unmonitored paths or violating origin checks return **403 Forbidden**.

| Endpoint | Method | Parameters / Body | Description |
|:---|:---:|:---|:---|
| `/` | `GET` | `launch: Optional[str]` | Serves frontend index HTML; validates one-time launch token, sets session cookie, and redirects with 303. |
| `/api/search` | `GET` | `query: str`, `personalize: bool = True` | Main search endpoint executing routing, retrieval, score fusion, and personalization. |
| `/api/recommendations`| `GET` | `limit: int = 4` | Retrieves proactive zero-query file suggestions ranked by affinity scoring. |
| `/api/horizons` | `GET` | None | Lists all registered monitored directory horizons with file counts and scan timestamps. |
| `/api/horizons` | `POST` | `{"path": "D:\\Projects"}` | Adds a new monitored folder horizon, triggers security checks, and scans its files. |
| `/api/horizons` | `DELETE`| `path: str` | Removes a monitored folder horizon and unindexes its associated files. |
| `/api/scan` | `POST` | `{"directory_path": "...", "force": bool}` | Scans or re-indexes a specific directory path. |
| `/api/scan-all` | `POST` | `force: bool = False` | Re-scans all registered monitored folder horizons across storage drives. |
| `/api/log-access` | `POST` | `{"filepath": "..."}` | Validates normalized path against index & horizons; launches safe files or reveals executable files in Explorer. |
| `/api/stats` | `GET` | None | Returns total indexed files, total queries logged, and average system latency. |

---

## 8. Current Technical Boundaries & What is NOT Yet Implemented

To give a clear baseline for Phase 2 development, here are the architectural boundaries of the current implementation:

1. **File Modification Monitoring**: Scanning is currently poll/trigger-based (on startup or via manual "Scan Folders" button). There is no active filesystem event daemon (e.g., `watchdog` monitoring in the background).
2. **Document Types Supported**: Supports `.txt`, `.md`, `.pdf`, `.docx`, and major code formats (`.py`, `.js`, `.cpp`, `.html`, `.json`, etc.). It does **not** yet perform OCR on image files (`.png`, `.jpg`, `.tiff`) or extract text from presentations (`.pptx`) or spreadsheets (`.xlsx`).
3. **Chunking Strategy**: Documents are currently embedded as single cohesive representations (or truncated top sections). There is no fine-grained chunk-level retrieval with sliding windows.
4. **Interactive Chat / RAG**: Compass is currently an **intelligent search and recommendation system**, not an interactive conversation agent (i.e., users cannot ask questions like *"summarize section 3 of my meeting minutes"* directly in the UI).
5. **Multi-Modal Embeddings**: No CLIP/image vector embeddings for searching diagrams or pictures by natural language.
6. **OS Distribution Packaging**: Runs locally via Python/Uvicorn server. Not yet bundled into an installer (`.exe` / `.msi` via PyInstaller/InnoSetup) with system tray integration and a global keyboard hook (`Cmd/Ctrl + Space`).

---

## 9. Questions & Focus Areas for Claude (Next Steps Guidance)

*Prompt for Claude when evaluating this specification:*

> **"Given this complete technical architecture, empirical performance, and current implementation status of Compass, please analyze:**
> 1. **Immediate High-Impact Enhancements (Phase 2)**: What are the most practical engineering additions to make this system competitive with tools like Raycast, Apple Spotlight, and Command E?
> 2. **Advanced Agentic AI Workflows**: How can we evolve this from retrieval into an autonomous agent (e.g., automated document clustering, cross-file synthesis, proactive task reminders, local RAG question-answering via Ollama/Llama 3)?
> 3. **Performance & Scaling**: What optimizations are needed if the index scales from 1,000 files to 100,000+ files across multiple physical drives?
> 4. **Packaging & Desktop Integration**: What is the cleanest architecture to distribute this as a lightweight native background daemon with a global OS hotkey?"*
