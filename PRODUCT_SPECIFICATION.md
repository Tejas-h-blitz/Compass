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
| `/api/index/status` | `GET` | None | Returns live indexing daemon state (`idle`\|`indexing`\|`reconciling`\|`paused`\|`error`), queue depth, files processed, errors, and `current_file`. |
| `/api/index/pause` | `POST` | None | Pauses the live indexing worker (events continue accumulating in the debounce queue). |
| `/api/index/resume` | `POST` | None | Resumes a paused live indexing worker. |
| `/api/index/rescan` | `POST` | None | Queues an immediate full reconcile walk of all monitored roots. |
| `/api/monitored` | `GET` | None | Lists all monitored roots with their watchdog observer status and last-scanned timestamp. |
| `/api/system/known-folders` | `GET` | None | Returns Windows known folders (Desktop, Documents, Downloads, Pictures, Videos) with existence flags. |
| `/api/system/pick-folder` | `POST` | `{"start_path": "..."}` | Opens a native Windows folder-picker dialog and returns the selected path. |
| `/api/system/info` | `GET` | None | Returns OS platform, Python version, total indexed files, and demo-mode flag. |
| `/api/demo/activate` | `POST` | None | Switches the running profile to demo mode, sets up sample corpus, seeds history. |
| `/api/demo/deactivate` | `POST` | None | Returns the running profile to normal mode. |
| `/api/demo/status` | `GET` | None | Returns `{"active": bool, "corpus_path": str, "suggested_queries": [...]}`. |

---

---

## 8. Application Shell Architecture (Phase 2B)

Compass features an installed background application shell designed for seamless Windows desktop integration:

| Component | Status | Implementation Details |
|:---|:---:|:---|
| **System Tray Resident** | **Implemented** | Managed via `pystray` with dynamically drawn 64x64 RGBA Pillow compass icon (accent blue `#3b82f6` ring and directional needle). Main thread owns the tray event loop while Uvicorn, hotkey, and event listener run on daemon threads. Closing the UI window does not terminate the process. Menu provides: *Open Compass* (default), *Rescan folders*, *Start with Windows* (checkable), *Open logs folder*, and *Quit Compass* (clean graceful shutdown with 5s watchdog). |
| **Single Instance Enforcement** | **Implemented** | Win32 per-session named mutex `Local\CompassSingleInstance` via `CreateMutexW`. Secondary launches detect `ERROR_ALREADY_EXISTS (183)`, signal named event `Local\CompassShowWindow`, and exit cleanly with code 0. Primary instance listens via `WaitForSingleObject` and restores/focuses its existing window. |
| **Window Management & Dedicated Profile** | **Implemented** | Finds existing windows via `EnumWindows` and `GetWindowTextW`. Restores minimized windows (`ShowWindow(SW_RESTORE)`) and brings them to foreground (`SetForegroundWindow`). Launches Edge in app mode with an isolated dedicated profile: `--app=<fresh_url> --user-data-dir=%LOCALAPPDATA%\Compass\edge-profile --no-first-run --no-default-browser-check`, preventing cookie crosstalk and browser process handoffs. Falls back to Chrome or default system browser. |
| **Per-User Windows Autostart** | **Implemented** | Pure `winreg` implementation managing `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\Compass`. Automatically builds quoted command (`pythonw.exe app.py --background` in source mode, `<sys.executable> --background` when frozen). Single source of truth in registry; wired to tray checkbox. |
| **Configurable Global Hotkey** | **Implemented** | Dedicated thread running Win32 message loop (`RegisterHotKey` with `MOD_NOREPEAT` and `GetMessageW`). Default combo `ctrl+alt+space`. Pure string parser validates combinations (ctrl, alt, shift, win + letters, digits, F1-F12, space) and rejects bare keys. Conflict-resilient: if hotkey is already registered by another app, logs warning and raises tray notification without crashing. |
| **Paths, Settings & Logging Foundations** | **Implemented** | Single source of truth in `backend/paths.py`. Persistent home under `%LOCALAPPDATA%\Compass` containing `logs/compass.log` (`RotatingFileHandler` 1MB x 3 backups with `pythonw` stdout/stderr redirection and `log_config=None` for Uvicorn), `edge-profile/`, and `settings.json` (atomic file replacement and `.bak` corruption recovery). Dynamic runtime port selection (`choose_port(8000)`) with synchronized Host/Origin middleware validation. |

### Known Limitations
1. **Windows Platform Only**: Desktop shell components (`backend/platform/*`) interface directly with Win32 `ctypes` and `winreg`. macOS / Linux ports require platform-specific stubs (`NotImplementedError` raised).
2. **Foreground Focus Restrictions**: Under Windows foreground activation locks (e.g. `LockSetForegroundWindow`), `SetForegroundWindow` may be restricted by the OS if invoked from a background hotkey or secondary process. Compass gracefully falls back to `FlashWindowEx` to flash the window and taskbar item.
3. **Hotkey Conflicts**: Global hotkeys require exclusive OS registration. If another running program owns `ctrl+alt+space`, registration fails gracefully; Compass logs the conflict and notifies the user to adjust `settings.json`.

---

## 9. Current Technical Boundaries & What is NOT Yet Implemented

To give a clear baseline for future development, here are the architectural boundaries of the current implementation:

1. **File Modification Monitoring**: ~~Scanning is currently poll/trigger-based.~~ **Now implemented (Phase 2C)**: Live incremental indexing via `watchdog` observers with debouncing — see §10.
2. **Document Types Supported**: Supports `.txt`, `.md`, `.pdf`, `.docx`, and major code formats (`.py`, `.js`, `.cpp`, `.html`, `.json`, etc.). It does **not** yet perform OCR on image files (`.png`, `.jpg`, `.tiff`) or extract text from presentations (`.pptx`) or spreadsheets (`.xlsx`).
3. **Chunking Strategy**: Documents are currently embedded as single cohesive representations (or truncated top sections). There is no fine-grained chunk-level retrieval with sliding windows.
4. **Interactive Chat / RAG**: Compass is currently an **intelligent search and recommendation system**, not an interactive conversation agent (i.e., users cannot ask questions like *"summarize section 3 of my meeting minutes"* directly in the UI).
5. **Multi-Modal Embeddings**: No CLIP/image vector embeddings for searching diagrams or pictures by natural language.
6. **Installer Bundling**: Not yet bundled into an installer (`.msi` / `.exe` via InnoSetup or WiX).

---

## 10. Phase 2C — Live Indexing, Demo Mode & First-Run Onboarding (Day 3)

### 10.1  Live Incremental Indexing

**Goal**: Index file changes in real time as users work, with zero CPU spikes on bursts.

| Component | File | Description |
|:---|:---|:---|
| `IndexingService` | `backend/indexing/service.py` | Orchestrator: starts per-root `watchdog` observers, owns worker + scheduler threads. |
| `CompassWatchdogHandler` | `backend/indexing/service.py` | Converts `watchdog` FS events into debounced queue entries per root. |
| `Debouncer` | `backend/indexing/debounce.py` | Coalesces rapid event bursts; emits stable UPSERT/DELETE/MOVE jobs after `quiet_period` (default 1.5 s). Absorbs storms (> 500 events) into a single RECONCILE job. |
| `IndexingStatus` | `backend/indexing/status.py` | Thread-safe counters (`indexed`, `updated`, `pruned`, `skipped_cloud`, `errors`) and state machine (`idle` → `indexing` / `reconciling` → `idle`). |
| Ignore & Validation | `backend/indexing/rules.py`, `backend/indexing/validate.py` | `should_ignore()` filters system dirs, `.git`, `node_modules`, temp files, unsupported extensions. `validate_monitored_path()` enforces security guardrails (no drive roots, no `%APPDATA%`, no profile root, no Compass own dirs). |
| Thread Priority | `backend/platform/priority.py` | Worker runs at `THREAD_PRIORITY_BELOW_NORMAL` via Win32 `SetThreadPriority` to remain transparent during foreground use. |
| Startup Reconcile | `IndexingService._scheduler_loop` | On start, queues a full reconcile walk of all monitored roots to catch offline changes. Periodic reconcile every 6 hours thereafter. |

**Ignore rules summary** (`should_ignore`):
- Compass own dirs (`data_dir()`, `app_home()`) are always excluded.
- Dir names: `.git`, `node_modules`, `.venv`, `venv`, `__pycache__`, `env`, `.next`, `dist`, `build`, `.idea`, `.vscode`, `$recycle.bin`, `system volume information`, `.ssh`, `.aws`.
- Temp/lock file patterns: `~$*`, `.~lock.*`, `*.tmp`, `*.crdownload`, `*.part`, `*.partial`, `Thumbs.db`, `desktop.ini`.
- Unsupported extensions (only indexing `.txt`, `.md`, `.pdf`, `.docx`, `.py`, `.js`, `.ts`, `.html`, `.css`, `.java`, `.c`, `.cpp`, `.h`, `.json`, `.yaml`, `.yml`, `.csv`).
- Symlinks and junction points.
- OneDrive Files-On-Demand (`FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS` / `FILE_ATTRIBUTE_RECALL_ON_OPEN`): file is indexed with empty content rather than triggering a cloud download.

**Tray integration**: The *Pause Indexing* / *Resume Indexing* / *Rescan Now* tray items control the live indexing daemon.

### 10.2  Demo Mode

**Goal**: Let a first-time user explore Compass with realistic content before adding their own folders.

| Aspect | Detail |
|:---|:---|
| **Corpus** | 50+ synthetic CS student files under `sample_corpus/` (`.txt`, `.md`, `.pdf`, `.docx`, `.py`, `.json`, `.csv`, `.html`). Files span `days_ago` 1–90 for realistic recency distribution. |
| **Manifest** | `sample_corpus/manifest.json` declares `version`, per-file `days_ago` values, and 8 `suggested_queries` with `expected` top result. |
| **Profile isolation** | Demo profile is a separate SQLite + ChromaDB instance under `app_home()/demo/`. Activating demo switches `COMPASS_DATA_DIR` at runtime (no process restart required). |
| **Setup** | `setup_demo_corpus_if_needed()` copies source files, applies synthetic `os.utime()` timestamps, registers the corpus dir as a monitored root. Idempotent: skips rebuild if `.corpus_version` marker matches manifest. |
| **Simulated history** | `seed_simulated_history()` inserts realistic `access_log` entries (15 records across 4 representative files) so recommendations work on first launch. |
| **UI indicators** | Amber demo-mode banner with a *Deactivate Demo* button. Suggested-queries grid shows all 8 manifest queries as clickable chips. |
| **Security** | `seed_simulated_history()` raises `PermissionError` if called outside demo mode. Demo corpus directory is safety-checked to be strictly inside `app_home()/demo/` before any file deletion. |

### 10.3  First-Run Onboarding Wizard

A five-step modal wizard presented on first launch (or when `settings.json` `"onboarding_complete": false`):

| Step | Content |
|:---:|:---|
| 1 | **Welcome** — hero illustration, feature highlights (semantic search, live sync, personalization). |
| 2 | **Demo Mode** — option to explore with sample content or skip straight to folder setup. |
| 3 | **Add Folders** — integrates with Windows known-folder shortcuts (Desktop, Documents, Downloads); shows native folder picker. |
| 4 | **Privacy** — explains local-first architecture; all embeddings stored on device; no cloud sync. |
| 5 | **Ready** — completion confirmation; first scan queued automatically. |

### 10.4  Folder Manager UI

Accessed via the ⚙ Settings panel:
- Lists all monitored roots with file count and last-indexed timestamp.
- ➕ **Add Folder** button opens native OS folder picker via `/api/system/pick-folder`.
- ✕ **Remove** with a confirmation modal (warns that index entries for that folder will be deleted).
- Live progress bar driven by SSE polling `/api/index/status` at 1 Hz.

### 10.5  Measured Performance (Day 3 Benchmarks)

| Metric | Result | Methodology |
|:---|:---:|:---|
| Index throughput | **~120 files/s** | `tools/measure_index_throughput.py`: 200 synthetic `.txt` files, forced re-scan, wall-clock timing. |
| Watchdog event-to-index latency (P50) | **< 2.0 s** | `tools/measure_watch_latency.py`: 20 file-write events, median `mtime` → DB-visible latency. |
| Watchdog event-to-index latency (P95) | **< 4.5 s** | Same tool, 95th percentile (includes ChromaDB embedding cold-start on first event). |
| Demo corpus setup time | **< 3 s** | 50 files copied + utime applied in-process. |
| Onboarding first-render | **< 100 ms** | Static HTML/CSS; no blocking network calls. |

> **Retrieval regression**: All 16 eval queries continue to pass at the same recall@3 as Phase 2B baseline (confirmed by `eval/run_eval.py`). Live indexing code does not touch any retrieval, router, fusion, or personalization logic.

### 10.6  Day 3 Git History

| Commit | SHA (short) | Description |
|:---|:---:|:---|
| Task 1 | `540b40e` | `feat: indexing foundations — ignore rules, path validation, WAL mode` |
| Task 2 | `e4d4f8e` | `feat: live IndexingService — watchdog, debouncer, reconcile, priority` |
| Task 3 | `19141e6` | `feat: index API & tray integration — status, pause, resume, rescan, monitored, system` |
| Task 4 | `f1371b7` | `feat: demo mode — isolated profile, sample corpus, manifest, suggested queries` |
| Task 5 | `ecf58d6` | `feat: frontend — onboarding wizard, folder manager, index progress bar, demo banner` |
| Task 6 | *(pending)* | `test: add indexing, demo and validation tests; docs: update spec` |

---

## 11. Questions & Focus Areas (Next Steps Guidance)

*Prompt for Claude when evaluating this specification:*

> **"Given this complete technical architecture, empirical performance, and current implementation status of Compass, please analyze:**
> 1. **Immediate High-Impact Enhancements (Phase 2)**: What are the most practical engineering additions to make this system competitive with tools like Raycast, Apple Spotlight, and Command E?
> 2. **Advanced Agentic AI Workflows**: How can we evolve this from retrieval into an autonomous agent (e.g., automated document clustering, cross-file synthesis, proactive task reminders, local RAG question-answering via Ollama/Llama 3)?
> 3. **Performance & Scaling**: What optimizations are needed if the index scales from 1,000 files to 100,000+ files across multiple physical drives?
> 4. **Packaging & Desktop Distribution**: What is the cleanest architecture to package and sign this as a standalone desktop binary (.msi/.exe installer)?"*
