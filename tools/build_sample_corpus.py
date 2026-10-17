import os
import sys
import json
import random
from pathlib import Path
from fpdf import FPDF
from docx import Document

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample_corpus"))

# Synthetic CS student documents data
DOCUMENTS = [
    # 1. PDFs (12 files)
    {
        "filename": "kubernetes_guide.pdf",
        "type": "pdf",
        "days_ago": 5,
        "tags": ["devops", "cloud", "kubernetes"],
        "title": "Comprehensive Guide to Kubernetes Architecture and Deployments",
        "content": (
            "Kubernetes is an open-source container orchestration platform designed to automate deploying, "
            "scaling, and operating application containers. At its core, a Kubernetes cluster consists of control plane "
            "components and worker nodes. The control plane runs the API Server (kube-apiserver), which validates and "
            "configures data for objects such as pods, services, and replication controllers. The etcd distributed key-value "
            "store provides reliable state storage. The kube-scheduler observes newly created Pods and assigns them to nodes "
            "based on resource requirements, constraints, and affinity specifications.\n\n"
            "Worker nodes host the components responsible for running containerized workloads: the kubelet agent, kube-proxy network "
            "proxy, and the container runtime (such as containerd). Pods are the smallest deployable computing units. Higher-level "
            "abstractions like Deployments declare desired state, enabling declarative zero-downtime rolling updates. Services "
            "provide stable IP addresses and DNS names to route traffic to dynamic pod endpoints. Ingress controllers manage "
            "external HTTP/S access into the cluster, providing load balancing, SSL/TLS termination, and name-based virtual hosting."
        )
    },
    {
        "filename": "spring_break_itinerary.pdf",
        "type": "pdf",
        "days_ago": 12,
        "tags": ["travel", "personal", "california"],
        "title": "Pacific Coast Highway Spring Break Road Trip Itinerary",
        "content": (
            "Spring break road trip schedule along California Highway 1 with Maya and Jordan. "
            "Day 1: Depart San Francisco early morning, drive south towards Monterey Bay. Stop at Santa Cruz boardwalk, "
            "explore Monterey Bay Aquarium in the afternoon, dinner at Fisherman's Wharf. "
            "Day 2: Morning scenic drive along 17-Mile Drive through Pebble Beach and Cypress Point. Enter Big Sur region, "
            "stop for iconic photography at Bixby Creek Bridge, hike McWay Falls trail at Julia Pfeiffer Burns State Park. "
            "Camp overnight at Pfeiffer Big Sur campground.\n\n"
            "Day 3: Continue south through San Simeon with an afternoon tour of Hearst Castle. Drive past Morro Rock, "
            "check into beachfront inn at Pismo Beach for evening sunset bonfire and clam chowder. "
            "Day 4: Morning dune buggy riding at Oceano Dunes, afternoon drive down through Santa Barbara wine country. "
            "Explore historic Santa Barbara Mission and State Street for dinner. "
            "Day 5: Relaxed coastal cruise into Malibu and Santa Monica pier, return drive back to campus via Interstate 5."
        )
    },
    {
        "filename": "resume_2024.pdf",
        "type": "pdf",
        "days_ago": 18,
        "tags": ["career", "resume"],
        "title": "Alex Chen - Curriculum Vitae (2024 Software Engineering)",
        "content": (
            "Alex Chen | Computer Science Senior | alex.chen@student.edu | github.com/alexchen-dev\n\n"
            "Education: B.S. in Computer Science, Magna Cum Laude, GPA 3.89. Relevant Coursework: Distributed Systems, "
            "Database Implementation, Operating Systems, Algorithm Analysis, Machine Learning, Computer Networks.\n\n"
            "Technical Skills: Python, Go, C++, Rust, TypeScript, FastAPI, PostgreSQL, SQLite, ChromaDB, Redis, Docker, Kubernetes.\n\n"
            "Experience: Software Engineering Intern at CloudScale Infrastructure (Summer 2023). Built high-throughput telemetry "
            "ingestion pipeline using Go and gRPC, reducing latency by 35%. Implemented distributed tracing across microservices.\n\n"
            "Undergraduate Research Assistant at Systems Lab (2022 - Present). Researched LSM-tree compaction heuristics and SSD write "
            "amplification mitigation under Professor Vance. Co-authored workshop paper on adaptive cache partitioning algorithms."
        )
    },
    {
        "filename": "cover_letter_google.pdf",
        "type": "pdf",
        "days_ago": 22,
        "tags": ["career", "application"],
        "title": "Software Engineering Cover Letter - Google University Graduate",
        "content": (
            "Dear University Recruiting Team,\n\n"
            "I am writing to express my enthusiastic interest in the Software Engineer, University Graduate position at Google. "
            "As a senior studying Computer Science with deep hands-on experience in distributed systems and systems performance, "
            "I have long admired Google's engineering culture and foundational contributions to computing, from MapReduce and Spanner "
            "to Borg and modern tensor processing architectures.\n\n"
            "Throughout my academic and internship career, I have focused on solving thorny systems problems. Last summer at CloudScale, "
            "I overhauled a distributed event processing service handling over fifty thousand transactions per second. At my university "
            "systems lab, I implemented a Raft consensus engine and evaluated its partition recovery guarantees. I thrive when profiling "
            "low-level bottlenecks and designing robust software that scales gracefully under real-world load."
        )
    },
    {
        "filename": "doc4.pdf",
        "type": "pdf",
        "days_ago": 30,
        "tags": ["distributed_systems", "notes", "algorithms"],
        "title": "Clock Synchronization and Vector Clocks in Distributed Systems",
        "content": (
            "In distributed systems without shared memory or a single synchronized physical clock, ordering events across independent "
            "processes represents a fundamental challenge. Physical quartz clocks suffer from clock drift caused by temperature "
            "fluctuations and hardware imperfections. Network Time Protocol (NTP) synchronizes clocks across packet networks via statistical "
            "jitter filtering, but bounds cannot guarantee strict global ordering for causal consistency.\n\n"
            "Leslie Lamport introduced logical clocks where each process maintains a monotonically increasing integer counter. If event A "
            "causally precedes event B (happened-before relation, denoted A -> B), then L(A) < L(B). However, the converse does not hold: "
            "L(A) < L(B) does not imply causal relationship. Vector Clocks resolve this deficiency by having each node maintain a vector of "
            "clock values for all nodes in the cluster. Incrementing the local index on internal events and transmitting the vector with every "
            "message allows nodes to detect concurrent operations, establish partial orders, and resolve split-brain conflicts."
        )
    },
    {
        "filename": "operating_systems_cfs_notes.pdf",
        "type": "pdf",
        "days_ago": 35,
        "tags": ["os", "linux", "scheduling"],
        "title": "Linux Completely Fair Scheduler (CFS) Deep Dive",
        "content": (
            "The Linux Completely Fair Scheduler (CFS), introduced in kernel 2.6.23 by Ingo Molnar, replaces traditional multi-level "
            "feedback priority queues with an elegant ideal multi-tasking model. CFS models an 'ideal multi-tasking CPU' where each "
            "runnable process receives an equal share of CPU cycles simultaneously. Because hardware consists of discrete processor cores, "
            "CFS tracks virtual runtime (vruntime) for each task.\n\n"
            "A process's vruntime represents the amount of execution time spent on the CPU scaled inversely by its nice level (priority weight). "
            "CFS organizes runnable tasks inside a self-balancing red-black tree (rb-tree) keyed strictly by vruntime. The leftmost node of "
            "the tree is always the process with the smallest vruntime—the task most entitled to CPU time next. When a running task consumes "
            "CPU cycles, its vruntime increases, and it is re-inserted into the tree. Granularity knobs ensure context switch overhead remains "
            "bounded while maintaining sub-millisecond fairness."
        )
    },
    {
        "filename": "distributed_transactions_2pc.pdf",
        "type": "pdf",
        "days_ago": 40,
        "tags": ["database", "distributed_systems", "consensus"],
        "title": "Two-Phase Commit (2PC) and Consensus Protocols in Distributed Databases",
        "content": (
            "Distributed transactions spanning multiple autonomous database partitions require atomic commitment protocols to ensure "
            "that either all participating nodes commit the transaction or all abort it (Atomicity). The classic Two-Phase Commit (2PC) "
            "protocol consists of a coordinator and multiple cohort participants.\n\n"
            "Phase 1: Prepare Phase. The coordinator sends a Prepare message to all cohorts. Each cohort checks local constraints, locks "
            "necessary rows, flushes undo/redo log records to persistent storage, and votes YES (prepared) or NO (abort). "
            "Phase 2: Commit Phase. If every cohort voted YES, the coordinator logs a COMMIT record to disk and broadcasts Commit to cohorts. "
            "If any cohort voted NO or timed out, the coordinator broadcasts Abort. The primary limitation of standard 2PC is that it is a "
            "blocking protocol: if the coordinator crashes after cohorts enter the PREPARED state, cohorts must wait indefinitely for recovery."
        )
    },
    {
        "filename": "compilers_ast_optimization.pdf",
        "type": "pdf",
        "days_ago": 45,
        "tags": ["compilers", "optimization", "cs"],
        "title": "Abstract Syntax Trees and SSA Intermediate Representation",
        "content": (
            "Modern compiler backends transform raw source code through several phases: lexical analysis, syntactic parsing, semantic "
            "analysis, intermediate code generation, optimization passes, and target machine code generation. The parser produces an "
            "Abstract Syntax Tree (AST) capturing the nested hierarchical grammar of expressions, statements, and blocks.\n\n"
            "For aggressive optimization, modern compilers (like LLVM and GCC) convert ASTs into Static Single Assignment (SSA) form. "
            "In SSA form, every variable is assigned a value exactly once, and every use is explicitly dominated by its unique definition. "
            "Where control flow paths converge (e.g., following an if-else branch or loop header), phi functions mathematically merge "
            "competing definitions. SSA vastly simplifies dataflow analyses such as common subexpression elimination, constant folding, "
            "dead code elimination, and loop-invariant code motion."
        )
    },
    {
        "filename": "linear_algebra_svd_notes.pdf",
        "type": "pdf",
        "days_ago": 50,
        "tags": ["math", "linear_algebra", "ml"],
        "title": "Singular Value Decomposition (SVD) and Principal Component Analysis",
        "content": (
            "Singular Value Decomposition (SVD) represents one of the most powerful theorems in applied linear algebra. Given any real "
            "m-by-n matrix A, SVD decomposes it into the product of three canonical matrices: A = U * Sigma * V^T, where U is an m-by-m "
            "orthogonal matrix of left singular vectors, Sigma is an m-by-n diagonal matrix containing non-negative singular values sorted in "
            "descending order, and V^T is the transpose of an n-by-n orthogonal matrix of right singular vectors.\n\n"
            "In data science and dimensionality reduction, SVD forms the mathematical foundation of Principal Component Analysis (PCA). "
            "The top singular values quantify the variance of data points projected along the corresponding singular vectors. By truncating "
            "Sigma to retain only the top k singular values, we obtain the optimal low-rank approximation of matrix A under the Frobenius norm "
            "(Eckart-Young-Mirsky theorem), filtering noise while compressing multidimensional embeddings."
        )
    },
    {
        "filename": "computer_vision_yolo_survey.pdf",
        "type": "pdf",
        "days_ago": 55,
        "tags": ["ai", "vision", "deep_learning"],
        "title": "Evolution of Real-Time Object Detection: From YOLOv1 to Modern Detectors",
        "content": (
            "Real-time object detection models must solve two simultaneous tasks: identifying what objects are present in an image "
            "(classification) and predicting bounding box spatial coordinates (localization). Early approaches used two-stage detectors "
            "like R-CNN and Faster R-CNN, generating sparse region proposals followed by convolutional classification, which limited frame rates.\n\n"
            "The You Only Look Once (YOLO) architecture revolutionized computer vision by framing detection as a single regression problem "
            "directly from image pixels to bounding box coordinates and class probabilities. By dividing the input image into an S-by-S grid "
            "and computing predictions in a single forward pass, YOLO achieved high frame rates suitable for real-time video feeds. Later "
            "iterations introduced anchor boxes, feature pyramid networks (FPN), path aggregation networks (PANet), and mosaic data augmentations."
        )
    },
    {
        "filename": "security_pki_cryptography.pdf",
        "type": "pdf",
        "days_ago": 60,
        "tags": ["security", "crypto", "networks"],
        "title": "Public Key Infrastructure (PKI) and TLS 1.3 Handshake Mechanics",
        "content": (
            "Transport Layer Security (TLS) safeguards confidentiality, data integrity, and mutual authentication across internet communications. "
            "Public Key Infrastructure (PKI) establishes trust between parties through hierarchical Certificate Authorities (CAs). A server "
            "proves ownership of an identity through an X.509 digital certificate signed by an intermediary CA whose root is trusted in the client's "
            "local trust store.\n\n"
            "TLS 1.3 substantially improved both speed and security compared to TLS 1.2 by eliminating insecure cryptographic primitives "
            "(such as static RSA key exchange and CBC-mode ciphers) and streamlining the initial handshake from two round trips down to a single "
            "round trip (1-RTT). The client sends supported cipher suites alongside a Diffie-Hellman key share in the ClientHello. The server selects "
            "the cipher, generates its own key share, computes the shared symmetric key, and transmits encrypted handshake extensions."
        )
    },
    {
        "filename": "database_internals_wal.pdf",
        "type": "pdf",
        "days_ago": 65,
        "tags": ["database", "storage", "wal"],
        "title": "Write-Ahead Logging and Recovery Algorithms for ACID Guarantees",
        "content": (
            "Write-Ahead Logging (WAL) is the cornerstone mechanism by which modern relational databases (including SQLite and PostgreSQL) "
            "guarantee durability and atomicity under unexpected system crashes or power failures. The fundamental WAL rule dictates that any "
            "modification to a database data page must be appended to the append-only log on non-volatile disk before the corresponding page can "
            "be flushed from the in-memory buffer pool to the main database file.\n\n"
            "During crash recovery, the database executes the classic ARIES recovery protocol, consisting of three sequential phases: "
            "1. Analysis phase: Scans the log forward from the last checkpoint to identify dirty pages in buffer pool and active uncommitted "
            "transactions at the moment of the crash. "
            "2. Redo phase: Replays history forward from the earliest unwritten log record, repeating every logged operation to bring the database "
            "state back to the exact instant of the crash. "
            "3. Undo phase: Scans backward, undoing the operations of all transactions that were still active when the crash occurred."
        )
    },

    # 2. DOCX (10 files)
    {
        "filename": "course_project_proposal.docx",
        "type": "docx",
        "days_ago": 8,
        "tags": ["coursework", "distributed_systems", "project"],
        "title": "CS 452 Final Project Proposal: Fault-Tolerant Distributed Key-Value Store",
        "content": (
            "Course: CS 452 Distributed Systems Engineering. Team Members: Alex Chen, Marcus Vance.\n\n"
            "Project Title: K-Store: An LSM-Tree Backed Distributed Key-Value Store with Raft Consensus.\n\n"
            "Executive Summary: We propose to design, implement, and benchmark a fault-tolerant, horizontally partitioned distributed key-value "
            "store written in Go. Distributed storage systems must balance consistency, availability, and partition tolerance. Our project will "
            "implement a leader-based Raft consensus group responsible for replication, log compaction, dynamic cluster membership changes, "
            "and automatic leader election upon node failure.\n\n"
            "Storage Engine Architecture: Instead of using in-memory hash tables, each individual storage node will feature a custom Log-Structured "
            "Merge-tree (LSM-tree) storage engine. The engine will buffer writes in an in-memory MemTable backed by an append-only WAL. When the "
            "MemTable reaches 16MB, it will freeze into an immutable SSTable file on disk with Bloom filters for single-seek key lookups. "
            "Evaluation Plan: We will deploy our 5-node cluster across multiple cloud availability zones and inject network partitions using Jepsen "
            "to measure recovery latency, throughput degradation, and linearizability adherence."
        )
    },
    {
        "filename": "resume_final.docx",
        "type": "docx",
        "days_ago": 15,
        "tags": ["career", "resume"],
        "title": "Alex Chen Resume - Full Stack & Systems Engineering",
        "content": (
            "Alex Chen - Engineering Resume.\n"
            "Contact: alex.chen@student.edu | 555-019-2834 | San Jose, California.\n\n"
            "Professional Summary: Dedicated Computer Science student with practical experience building distributed backends, "
            "low-latency file indexers, and modern web applications. Passionate about systems architecture and software security.\n\n"
            "Selected Projects: Compass Local Search Agent (FastAPI, SQLite FTS5, Vector Search, Vanilla JS). Built an offline search application "
            "indexing local files using hybrid keyword and embedding retrieval models. Designed debounced file watchers and background tray shell.\n\n"
            "Distributed Key-Value Store (Go, Raft). Implemented consensus replication, heartbeats, snapshotting, and snapshot compaction.\n\n"
            "Honors & Awards: Dean's Honor List (6 Semesters), First Place Hackathon Winner (BayHacks 2023)."
        )
    },
    {
        "filename": "hackathon_planning.docx",
        "type": "docx",
        "days_ago": 20,
        "tags": ["hackathon", "planning", "ai"],
        "title": "BayHacks 2024 Project Planning: Local AI Code Assistant",
        "content": (
            "Hackathon Brainstorming Session: BayHacks 36-Hour Hackathon.\n"
            "Team: Alex (Systems Backend), Priya (Frontend / UI), Kevin (ML model fine-tuning).\n\n"
            "Product Concept: CodeCompanion - A 100% private, local code completion and intelligent search tool that operates completely offline "
            "without uploading proprietary company repositories to cloud endpoints.\n\n"
            "Architecture Breakdown: The backend service will run a lightweight quantized model (e.g., StarCoder-3B or Phi-2) using llama.cpp. "
            "A background file watcher monitors workspace files, extracting AST symbol tokens via tree-sitter. ChromaDB or FAISS stores symbol "
            "embeddings for semantic contextual awareness.\n\n"
            "Milestone Roadmap: Hours 0-6: Environment setup, model quantization, base FastAPI server. Hours 6-18: Tree-sitter symbol extraction "
            "and vector indexing pipeline. Hours 18-28: VS Code extension interface and websocket streaming. Hours 28-34: Demo polishing and pitch deck."
        )
    },
    {
        "filename": "rest_api_design_standards.docx",
        "type": "docx",
        "days_ago": 25,
        "tags": ["api", "backend", "architecture"],
        "title": "Engineering Standards: RESTful API Design and Error Handling",
        "content": (
            "This document establishes internal standards for designing RESTful HTTP APIs across backend microservices.\n\n"
            "Resource Naming Conventions: Use plural nouns for resources (/api/users, /api/documents). Sub-resources represent hierarchical "
            "relationships (/api/users/{id}/orders). HTTP verbs specify actions: GET for retrieval (safe, idempotent), POST for creation, "
            "PUT for complete replacement, PATCH for partial modification, and DELETE for removal.\n\n"
            "Idempotency and Safety: Mutating POST endpoints supporting payment or creation actions must accept an Idempotency-Key header. "
            "The server caches successful responses keyed by the token to guarantee that client network retries do not trigger duplicate processing.\n\n"
            "Error Payloads: APIs must return structured JSON error payloads containing code, human-readable message, and optional details array. "
            "Use standard HTTP status codes: 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 429 Too Many Requests."
        )
    },
    {
        "filename": "meeting_notes_capstone_sync.docx",
        "type": "docx",
        "days_ago": 32,
        "tags": ["notes", "team", "capstone"],
        "title": "Senior Capstone Project Weekly Sync Meeting Notes",
        "content": (
            "Date: October 12. Attendees: Alex Chen, Marcus Vance, Professor Wallace.\n\n"
            "Progress Review: Alex finalized the SQLite FTS5 integration and benchmarked BM25 keyword retrieval latency across a 20,000-document "
            "test corpus. Query latency remains under 4 milliseconds for 3-term boolean searches. Marcus implemented the sentence-transformers "
            "pipeline and created embedding chunks.\n\n"
            "Discussion Points: Professor Wallace inquired about handling OneDrive cloud-only files. Alex noted that reading cloud-only files on Windows "
            "triggers an unwanted physical download. Solution: Check file attributes for FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS before opening.\n\n"
            "Action Items for Next Week: 1. Finalize hybrid score normalization and reciprocal rank fusion. 2. Implement the single-instance "
            "Win32 named mutex. 3. Prepare midterm presentation slides."
        )
    },
    {
        "filename": "untitled_final.docx",
        "type": "docx",
        "days_ago": 38,
        "tags": ["ml", "optimization", "neural_networks"],
        "title": "Gradient Descent Optimization Algorithms: A Comparative Study",
        "content": (
            "Training modern deep neural networks requires optimizing high-dimensional non-convex objective loss surfaces. Standard Stochastic "
            "Gradient Descent (SGD) updates parameters in the direction of the negative gradient computed over a mini-batch of samples. While simple, "
            "SGD suffers from slow progress along ravines where surface curves much more steeply than along the ravine floor.\n\n"
            "Momentum methods accelerate SGD by accumulating exponentially decaying moving averages of past gradients, dampening oscillations and "
            "speeding through plateau regions. Adaptive gradient algorithms, such as AdaGrad, dynamically scale learning rates inversely proportional "
            "to the square root of the sum of past squared gradients. RMSprop and Adam (Adaptive Moment Estimation) improve upon AdaGrad by tracking "
            "both first (mean) and second (uncentered variance) moments with bias corrections, making them the standard default optimizer."
        )
    },
    {
        "filename": "cloud_native_microservices_architecture.docx",
        "type": "docx",
        "days_ago": 42,
        "tags": ["cloud", "microservices", "architecture"],
        "title": "Patterns for Resilient Cloud-Native Microservices",
        "content": (
            "Transitioning from monolithic applications to distributed microservices architectures introduces distinct resilience challenges. "
            "Network partitions, slow downstream dependencies, and cascading failures can compromise entire systems if defensive engineering "
            "patterns are not implemented.\n\n"
            "Circuit Breaker Pattern: A circuit breaker wraps remote network calls, tracking failure rates. When failures exceed a threshold, "
            "the breaker trips OPEN, immediately rejecting subsequent calls without burdening the failing service. After a timeout, it enters "
            "HALF-OPEN state to test service recovery.\n\n"
            "Bulkhead Pattern: Isolate resource pools (such as thread pools or memory buffers) so that a failure in one service domain does not "
            "exhaust resources required by healthy subsystems. Combined with exponential backoff jitter and client-side timeouts, services "
            "maintain graceful degradation."
        )
    },
    {
        "filename": "database_sharding_and_partitioning.docx",
        "type": "docx",
        "days_ago": 48,
        "tags": ["database", "scaling", "sharding"],
        "title": "Horizontal Database Sharding Strategies and Rebalancing",
        "content": (
            "When dataset size and query write throughput exceed the physical constraints of a single database server, organizations must "
            "partition data horizontally across independent database instances known as shards. Choosing the right shard key is critical.\n\n"
            "Range-based Sharding: Assigns contiguous ranges of keys to specific shards (e.g., user IDs 1-1000000 on Shard A). While range queries "
            "are efficient, this approach frequently creates hot-spotting when newly created sequential IDs disproportionately bombard the latest shard.\n\n"
            "Hash-based Sharding and Consistent Hashing: Hash-based partitioning maps keys to shards using hash functions. Consistent hashing arranges "
            "shards along a virtual ring structure. When nodes are added or removed, only K/N keys need to be migrated, minimizing rebalancing churn."
        )
    },
    {
        "filename": "senior_thesis_outline.docx",
        "type": "docx",
        "days_ago": 53,
        "tags": ["academics", "thesis", "research"],
        "title": "Undergraduate Senior Honors Thesis Outline: Local-First Vector Indexing",
        "content": (
            "Candidate: Alex Chen. Advisor: Dr. Raymond Vance. Department of Computer Science.\n\n"
            "Thesis Title: Resource-Constrained Vector Retrieval and Hybrid Search on Edge Devices.\n\n"
            "Chapter 1: Introduction. Motivation for local-first computing: data privacy, zero recurring cloud inference costs, and offline utility. "
            "Problem statement: Embedding transformers and vector indexes consume significant RAM and CPU cycles on consumer hardware.\n\n"
            "Chapter 2: Related Work. Survey of Approximate Nearest Neighbor (ANN) algorithms: HNSW graphs, Inverted File (IVF) indexes, and Product "
            "Quantization. Trade-offs between index build latency, memory footprint, and recall accuracy.\n\n"
            "Chapter 3: System Architecture. Design of Compass: hybrid fusion engine combining SQLite FTS5 inverted index with ONNX-quantized MiniLM.\n\n"
            "Chapter 4: Empirical Evaluation and Benchmarks. Precision-Recall curves, latency distributions, and memory profiling results."
        )
    },
    {
        "filename": "apartment_lease_notes.docx",
        "type": "docx",
        "days_ago": 58,
        "tags": ["personal", "housing"],
        "title": "Off-Campus Apartment Lease Agreement Notes and Checklist",
        "content": (
            "Apartment Address: 412 University Avenue, Apt 3B. Landlord Contact: Heritage Property Management.\n\n"
            "Lease Terms: 12-month fixed-term lease starting August 1. Monthly Rent: $2,400 split three ways ($800 per person between Alex, "
            "Jordan, and Marcus). Security deposit: One month's rent ($2,400) held in escrow account.\n\n"
            "Utilities Breakdown: Water, sewer, and trash removal included in base rent. Tenants responsible for electric (PG&E), gas, and high-speed "
            "fiber internet (Sonic 1Gbps, $60/month split equally).\n\n"
            "Move-in Inspection Checklist: Take comprehensive timestamped photos of baseboards, kitchen countertops, refrigerator interior, "
            "and bathroom tiles before moving furniture. Note pre-existing scuff on living room hardwood floor to prevent deposit disputes."
        )
    },

    # 3. Markdown (8 files)
    {
        "filename": "database_indexing_notes.md",
        "type": "md",
        "days_ago": 3,
        "tags": ["database", "b-trees", "indexes"],
        "title": "B-Trees, B+ Trees, and LSM-Trees: Database Indexing Fundamentals",
        "content": (
            "# Database Indexing Fundamentals: B-Trees and LSM-Trees\n\n"
            "Database indexes are specialized auxiliary data structures designed to minimize physical disk I/O operations when retrieving "
            "records based on search key attributes.\n\n"
            "## B-Trees and B+ Trees\n"
            "B-Trees are self-balancing multi-way search trees optimized for storage systems that read and write large blocks of data. "
            "In a standard B-Tree, internal nodes store both search keys and record pointers. In a **B+ Tree**, internal nodes store only "
            "routing keys and child pointers, while all data records (or heap pointers) reside exclusively in leaf nodes.\n\n"
            "Key advantages of B+ Trees:\n"
            "- Leaf nodes are linked sequentially via pointers, making full range scans efficient without traversing parent nodes.\n"
            "- Internal nodes have higher branching factor (fan-out), resulting in shallower tree height and fewer disk seeks (typically 3-4 levels).\n\n"
            "## LSM-Trees (Log-Structured Merge-Trees)\n"
            "While B+ Trees update in-place (causing random writes on disk), LSM-Trees optimize for write-heavy workloads by transforming random "
            "writes into sequential appends. Writes are buffered in memory (MemTable) and periodically flushed to immutable Sorted String Tables (SSTables)."
        )
    },
    {
        "filename": "paper_summary_transformers.md",
        "type": "md",
        "days_ago": 10,
        "tags": ["ai", "transformers", "paper_notes"],
        "title": "Paper Summary: Attention Is All You Need (Vaswani et al. 2017)",
        "content": (
            "# Paper Summary: Attention Is All You Need\n\n"
            "**Authors:** Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin.\n\n"
            "## Core Innovation\n"
            "Prior sequence transduction models relied heavily on complex recurrent neural networks (RNNs, LSTMs, GRUs) or convolutional "
            "networks. These architectures suffer from inherent sequential constraints: computations for time step t depend strictly on hidden "
            "state h_{t-1}, precluding parallelization across long context windows.\n\n"
            "The Transformer architecture dispenses entirely with recurrence, relying solely on **Self-Attention** mechanisms to compute "
            "representations of input sequences. Scaled Dot-Product Attention computes attention weights dynamically: Attention(Q, K, V) = "
            "softmax((Q * K^T) / sqrt(d_k)) * V.\n\n"
            "Multi-Head Attention allows the model to jointly attend to information from different representation subspaces at different positions."
        )
    },
    {
        "filename": "distributed_consensus_raft_notes.md",
        "type": "md",
        "days_ago": 16,
        "tags": ["distributed_systems", "raft", "consensus"],
        "title": "Understanding the Raft Consensus Protocol",
        "content": (
            "# Raft Consensus Protocol Overview\n\n"
            "Raft is a consensus algorithm designed by Diego Ongaro and John Ousterhout as an understandable alternative to Multi-Paxos.\n\n"
            "## Core Subproblems\n"
            "Raft decomposes consensus into three independent subproblems:\n"
            "1. **Leader Election:** When an existing leader fails or cluster initializes, a randomized election timer triggers candidate nomination.\n"
            "2. **Log Replication:** The elected leader accepts client write commands, appends them to its local log, and replicates log entries "
            "to follower nodes via AppendEntries RPCs.\n"
            "3. **Safety:** If any server has applied a particular log entry at a given index to its state machine, no other server may apply a "
            "different log entry for the same index.\n\n"
            "## Election Safety and Quorums\n"
            "To win an election, a candidate must gather votes from a strict majority (quorum, N/2 + 1) of cluster nodes. Randomized election "
            "timers (150ms-300ms) prevent split votes, ensuring rapid leader convergence."
        )
    },
    {
        "filename": "docker_cheat_sheet.md",
        "type": "md",
        "days_ago": 24,
        "tags": ["devops", "docker", "containers"],
        "title": "Docker and Container Runtime Practical Reference Sheet",
        "content": (
            "# Practical Docker Container Cheat Sheet\n\n"
            "## Essential Image Commands\n"
            "- `docker build -t app-name:v1 .` - Build container image using local Dockerfile.\n"
            "- `docker images` - List locally cached container images.\n"
            "- `docker rmi <image_id>` - Remove image from local store.\n\n"
            "## Container Lifecycle Management\n"
            "- `docker run -d -p 8080:80 --name web-app nginx:alpine` - Run container detached with port mapping.\n"
            "- `docker ps -a` - Inspect status of all containers.\n"
            "- `docker logs -f <container_name>` - Stream container standard output and error logs.\n"
            "- `docker exec -it <container_name> /bin/sh` - Attach interactive shell to running container.\n\n"
            "## Multi-stage Builds Best Practice\n"
            "Always utilize multi-stage builds to compile binaries in an SDK environment and copy only the compiled artifact into a minimal "
            "scratch or alpine runtime image, reducing attack surface and image size."
        )
    },
    {
        "filename": "git_workflow_standards.md",
        "type": "md",
        "days_ago": 28,
        "tags": ["git", "workflow", "collaboration"],
        "title": "Team Git Branching Strategy and Conventional Commits",
        "content": (
            "# Team Git Workflow and Branching Standards\n\n"
            "## Branching Model\n"
            "- `main` - Production-ready branch. Direct pushes are disabled; changes require approved pull requests.\n"
            "- `feature/<name>` - Short-lived feature development branches branched off main.\n"
            "- `fix/<issue-id>` - Bug fix branches with targeted regression tests.\n\n"
            "## Conventional Commit Syntax\n"
            "Commit messages must follow the Conventional Commits specification:\n"
            "- `feat: add debounce file watcher to indexing service`\n"
            "- `fix: resolve SQLite busy timeout during concurrent WAL access`\n"
            "- `test: add end-to-end integration test for search router`\n"
            "- `docs: update product specification with incremental indexing numbers`\n\n"
            "Never rewrite history on shared branches (`git push --force` is prohibited on main)."
        )
    },
    {
        "filename": "networking_tcp_ip_fundamentals.md",
        "type": "md",
        "days_ago": 36,
        "tags": ["networking", "tcp", "protocols"],
        "title": "TCP/IP Transport Layer: Flow Control, Congestion Control, and Handshakes",
        "content": (
            "# TCP/IP Transport Layer Architecture\n\n"
            "Transmission Control Protocol (TCP) provides a reliable, ordered, and error-checked stream of octets over an unreliable "
            "packet network (IP).\n\n"
            "## Three-Way Handshake\n"
            "1. Client -> Server: `SYN` (Sequence Number = X)\n"
            "2. Server -> Client: `SYN-ACK` (Sequence Number = Y, Acknowledgment Number = X + 1)\n"
            "3. Client -> Server: `ACK` (Acknowledgment Number = Y + 1)\n\n"
            "## Flow Control vs Congestion Control\n"
            "- **Flow Control:** Prevents the sender from overwhelming the receiver's buffer. The receiver advertises its available buffer space "
            "via the `Receive Window (rwnd)` header field.\n"
            "- **Congestion Control:** Prevents senders from overwhelming the intermediate network infrastructure. Uses Slow Start, Congestion "
            "Avoidance (AIMD - Additive Increase Multiplicative Decrease), Fast Retransmit, and Fast Recovery algorithms."
        )
    },
    {
        "filename": "machine_learning_feature_engineering.md",
        "type": "md",
        "days_ago": 44,
        "tags": ["ml", "data", "features"],
        "title": "Practical Feature Engineering Techniques for Tabular Data",
        "content": (
            "# Practical Feature Engineering for Machine Learning\n\n"
            "Feature engineering transforms raw tabular data into representations that improve model learning capacity and predictive accuracy.\n\n"
            "## Numerical Preprocessing\n"
            "- **Standardization (Z-score scaling):** Transforms features to zero mean and unit variance. Critical for models sensitive to scale "
            "like SVMs, logistic regression, and neural networks.\n"
            "- **Robust Scaling:** Uses median and interquartile range (IQR), preventing outliers from skewing scaling boundaries.\n"
            "- **Log Transformation:** Normalizes highly skewed distributions (e.g. monetary amounts, website visit counts).\n\n"
            "## Categorical Encodings\n"
            "- **One-Hot Encoding:** For low-cardinality nominal variables without intrinsic ordinal ranking.\n"
            "- **Target Encoding:** Replaces categories with the expected target value, with smoothing to prevent overfitting."
        )
    },
    {
        "filename": "cybersecurity_owasp_top10.md",
        "type": "md",
        "days_ago": 52,
        "tags": ["security", "owasp", "web"],
        "title": "OWASP Top 10 Web Application Security Vulnerabilities",
        "content": (
            "# OWASP Top 10 Application Security Vulnerabilities\n\n"
            "Understanding common application vulnerabilities is essential for secure software engineering.\n\n"
            "1. **Broken Access Control:** Failures where users act outside their intended permissions (e.g., IDOR - Insecure Direct Object References).\n"
            "2. **Cryptographic Failures:** Exposure of sensitive data due to weak algorithms (MD5, SHA-1), hardcoded secrets, or lack of TLS.\n"
            "3. **Injection:** SQL, command, and LDAP injection where hostile data is parsed as commands. Remedy: Parameterized prepared statements.\n"
            "4. **Insecure Design:** Flaws inherent in architecture rather than code implementation, requiring threat modeling before coding.\n"
            "5. **Security Misconfiguration:** Default credentials, verbose error stack traces, unpatched dependencies, and missing security headers."
        )
    },

    # 4. TXT (6 files)
    {
        "filename": "notes_misc.txt",
        "type": "txt",
        "days_ago": 4,
        "tags": ["algorithms", "notes", "data_structures"],
        "title": "Miscellaneous CS Study Notes on Tree Balancing",
        "content": (
            "Study session notes on self-balancing binary search trees.\n"
            "AVL Trees: Strictly height-balanced. For every node, height of left and right subtrees differs by at most 1.\n"
            "Rotations: Left rotation, right rotation, left-right double rotation, right-left double rotation.\n"
            "Lookups are strictly O(log n) with smaller constant factors than Red-Black trees due to tighter height balance.\n"
            "Red-Black Trees: Slightly looser balance. Every node is red or black. Root is black. Red nodes cannot have red children.\n"
            "Every path from node to leaf contains same number of black nodes. Max height is 2 * log2(n + 1).\n"
            "Used extensively in Linux kernel, C++ std::map, and Java TreeMap because insertion and deletion require fewer rotations."
        )
    },
    {
        "filename": "healthy_meal_prep.txt",
        "type": "txt",
        "days_ago": 11,
        "tags": ["recipes", "cooking", "personal"],
        "title": "Budget Student Meal Prep and Quick Recipes",
        "content": (
            "Weekly Student Meal Prep Routine:\n\n"
            "Batch 1: Overnight Oats (Sunday Evening Prep)\n"
            "Combine rolled oats, chia seeds, oat milk, peanut butter, and a dash of cinnamon into 4 glass mason jars. "
            "Refrigerate overnight; top with sliced bananas or blueberries before morning classes.\n\n"
            "Batch 2: High-Protein Sheet Pan Fajita Bowls\n"
            "Dice chicken breast (or extra-firm tofu), bell peppers, and red onions into bite-sized strips. "
            "Toss in olive oil, smoked paprika, cumin, garlic powder, and lime juice. "
            "Roast on baking sheet at 400 degrees Fahrenheit for 25 minutes. Serve over brown rice with black beans and salsa.\n\n"
            "Quick Exam Night Ramen Upgrade:\n"
            "Boil standard instant noodles with vegetable broth. Whisk in a spoonful of miso paste, sesame oil, and sriracha. "
            "Drop in a soft-boiled egg and fresh green onions."
        )
    },
    {
        "filename": "resume_draft_v1.txt",
        "type": "txt",
        "days_ago": 26,
        "tags": ["career", "resume"],
        "title": "Alex Chen Resume Draft Scratchpad",
        "content": (
            "Draft notes for updating engineering resume:\n"
            "- Add bullet point about lowering SQLite busy timeouts in multi-threaded WAL mode.\n"
            "- Mention reciprocal rank fusion algorithm in Compass desktop search.\n"
            "- Update GPA after spring semester grade release.\n"
            "- Highlight open source contributions to watchdog and fpdf2 libraries.\n"
            "- Include link to GitHub profile and personal portfolio site.\n"
            "- Make sure contact email and phone number are formatted cleanly."
        )
    },
    {
        "filename": "laptop_setup_guide.txt",
        "type": "txt",
        "days_ago": 34,
        "tags": ["setup", "tools", "windows"],
        "title": "Fresh Windows Dev Environment Setup Instructions",
        "content": (
            "Steps for provisioning a new Windows 11 development machine:\n"
            "1. Install Windows Terminal and PowerShell 7 from Microsoft Store.\n"
            "2. Install Git for Windows with Git Credential Manager.\n"
            "3. Install VS Code and key extensions: Python, Pylance, Prettier, ESLint, Go.\n"
            "4. Install Python 3.11 with pip and set PATH variables.\n"
            "5. Enable WSL 2 (Windows Subsystem for Linux) with Ubuntu 22.04.\n"
            "6. Configure developer folder at D:\\projects to avoid OS drive bloat."
        )
    },
    {
        "filename": "reading_list_2024.txt",
        "type": "txt",
        "days_ago": 41,
        "tags": ["books", "reading", "personal"],
        "title": "Computer Science and Technical Books Reading List",
        "content": (
            "Books to complete this academic year:\n"
            "1. Designing Data-Intensive Applications by Martin Kleppmann (High Priority - Chapters 5, 7, 9).\n"
            "2. Operating Systems: Three Easy Pieces by Remzi and Andrea Arpaci-Dusseau (Virtualization & Concurrency).\n"
            "3. Database Internals by Alex Petrov (LSM-trees and B-Tree storage engines).\n"
            "4. Crafting Interpreters by Robert Nystrom (Lexing, parsing, and bytecode VMs).\n"
            "5. Clean Code by Robert C. Martin (Refactoring practices and code smells)."
        )
    },
    {
        "filename": "workout_routine_calisthenics.txt",
        "type": "txt",
        "days_ago": 49,
        "tags": ["fitness", "personal", "health"],
        "title": "Weekly Student Calisthenics and Cardio Routine",
        "content": (
            "Campus Recreation Center Fitness Routine:\n\n"
            "Monday - Upper Body Push:\n"
            "- Standard push-ups: 4 sets of 20 reps\n"
            "- Diamond push-ups: 3 sets of 15 reps\n"
            "- Parallel bar dips: 4 sets of 12 reps\n"
            "- Core: Hanging leg raises 3 sets of 12\n\n"
            "Wednesday - Upper Body Pull:\n"
            "- Wide-grip pull-ups: 4 sets of 8 reps\n"
            "- Chin-ups: 3 sets of 10 reps\n"
            "- Inverted rows: 3 sets of 12 reps\n\n"
            "Friday - Lower Body and Sprint Intervals:\n"
            "- Bodyweight squats and walking lunges\n"
            "- 5km outdoor trail run around campus lake."
        )
    },

    # 5. Code (5 files)
    {
        "filename": "benchmark_cache.py",
        "type": "code",
        "days_ago": 7,
        "tags": ["python", "code", "cache"],
        "title": "LRU and LFU Cache Benchmark Simulation Script",
        "content": (
            "import time\n"
            "from collections import OrderedDict\n\n"
            "class LRUCache:\n"
            "    def __init__(self, capacity: int):\n"
            "        self.capacity = capacity\n"
            "        self.cache = OrderedDict()\n\n"
            "    def get(self, key: str):\n"
            "        if key not in self.cache:\n"
            "            return -1\n"
            "        self.cache.move_to_end(key)\n"
            "        return self.cache[key]\n\n"
            "    def put(self, key: str, value: int):\n"
            "        if key in self.cache:\n"
            "            self.cache.move_to_end(key)\n"
            "        self.cache[key] = value\n"
            "        if len(self.cache) > self.capacity:\n"
            "            self.cache.popitem(last=False)\n\n"
            "if __name__ == '__main__':\n"
            "    cache = LRUCache(1000)\n"
            "    start = time.perf_counter()\n"
            "    for i in range(50000):\n"
            "        cache.put(f'key_{i % 1500}', i)\n"
            "    print(f'Execution completed in {time.perf_counter() - start:.4f}s')\n"
        )
    },
    {
        "filename": "debounce_helper.js",
        "type": "code",
        "days_ago": 14,
        "tags": ["javascript", "frontend", "utility"],
        "title": "JavaScript Frontend Input Debounce and Throttle Utility",
        "content": (
            "/**\n"
            " * Creates a debounced function that delays invoking func until after\n"
            " * wait milliseconds have elapsed since the last time the function was invoked.\n"
            " */\n"
            "export function debounce(func, wait = 250) {\n"
            "    let timeoutId;\n"
            "    return function executedFunction(...args) {\n"
            "        const context = this;\n"
            "        clearTimeout(timeoutId);\n"
            "        timeoutId = setTimeout(() => {\n"
            "            func.apply(context, args);\n"
            "        }, wait);\n"
            "    };\n"
            "}\n\n"
            "export function throttle(func, limit = 200) {\n"
            "    let inThrottle;\n"
            "    return function (...args) {\n"
            "        if (!inThrottle) {\n"
            "            func.apply(this, args);\n"
            "            inThrottle = true;\n"
            "            setTimeout(() => inThrottle = false, limit);\n"
            "        }\n"
            "    };\n"
            "}\n"
        )
    },
    {
        "filename": "memory_allocator.c",
        "type": "code",
        "days_ago": 21,
        "tags": ["c", "systems", "memory"],
        "title": "Simple C First-Fit Dynamic Memory Allocator",
        "content": (
            "#include <stdio.h>\n"
            "#include <stddef.h>\n"
            "#include <stdbool.h>\n\n"
            "typedef struct BlockHeader {\n"
            "    size_t size;\n"
            "    bool is_free;\n"
            "    struct BlockHeader* next;\n"
            "} BlockHeader;\n\n"
            "#define POOL_SIZE 65536\n"
            "static char memory_pool[POOL_SIZE];\n"
            "static BlockHeader* free_list = (BlockHeader*)memory_pool;\n\n"
            "void init_allocator() {\n"
            "    free_list->size = POOL_SIZE - sizeof(BlockHeader);\n"
            "    free_list->is_free = true;\n"
            "    free_list->next = NULL;\n"
            "}\n\n"
            "void* my_malloc(size_t size) {\n"
            "    BlockHeader* curr = free_list;\n"
            "    while (curr) {\n"
            "        if (curr->is_free && curr->size >= size) {\n"
            "            curr->is_free = false;\n"
            "            return (void*)((char*)curr + sizeof(BlockHeader));\n"
            "        }\n"
            "        curr = curr->next;\n"
            "    }\n"
            "    return NULL; // Out of memory\n"
            "}\n"
        )
    },
    {
        "filename": "schema_migrations.sql",
        "type": "code",
        "days_ago": 29,
        "tags": ["sql", "database", "schema"],
        "title": "PostgreSQL User Access and Telemetry Schema",
        "content": (
            "-- Database Migration: User Access and Search Telemetry Schema\n"
            "CREATE TABLE IF NOT EXISTS users (\n"
            "    id SERIAL PRIMARY KEY,\n"
            "    username VARCHAR(64) UNIQUE NOT NULL,\n"
            "    email VARCHAR(255) UNIQUE NOT NULL,\n"
            "    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP\n"
            ");\n\n"
            "CREATE TABLE IF NOT EXISTS query_telemetry (\n"
            "    id BIGSERIAL PRIMARY KEY,\n"
            "    query_text TEXT NOT NULL,\n"
            "    retrieval_strategy VARCHAR(32) NOT NULL,\n"
            "    latency_milliseconds DOUBLE PRECISION NOT NULL,\n"
            "    result_count INTEGER NOT NULL,\n"
            "    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP\n"
            ");\n\n"
            "CREATE INDEX idx_telemetry_strategy ON query_telemetry(retrieval_strategy);\n"
        )
    },
    {
        "filename": "app_config.json",
        "type": "code",
        "days_ago": 37,
        "tags": ["json", "config", "settings"],
        "title": "Development Environment Configuration Settings",
        "content": json.dumps({
            "appName": "CompassLocalSearch",
            "version": "0.3.0",
            "environment": "development",
            "search": {
                "hybridAlpha": 0.5,
                "topK": 10,
                "vectorMetric": "cosine",
                "recencyDecayHalfLifeDays": 7.0
            },
            "indexing": {
                "quietPeriodSeconds": 1.5,
                "stormThreshold": 500,
                "batchSize": 100
            }
        }, indent=2)
    },

    # 6. CSV and HTML (4 files)
    {
        "filename": "student_budget_2024.csv",
        "type": "csv",
        "days_ago": 6,
        "tags": ["budget", "finance", "student"],
        "title": "Monthly Student Living Expenses Breakdown (2024)",
        "content": (
            "Month,Category,Item,Amount,PaymentMethod,Notes\n"
            "September,Housing,Apartment Rent,800.00,Zelle,Split 3 ways\n"
            "September,Utilities,Sonic Fiber Internet,20.00,Debit Card,1Gbps split\n"
            "September,Groceries,Trader Joe's & Costco,340.50,Credit Card,Weekly meals\n"
            "September,Transportation,Caltrain Monthly Pass,95.00,Clipper Card,Student discount\n"
            "September,Academic,Textbooks & Supplies,125.00,Credit Card,Algorithm book\n"
            "October,Housing,Apartment Rent,800.00,Zelle,Split 3 ways\n"
            "October,Utilities,Sonic Fiber Internet,20.00,Debit Card,1Gbps split\n"
            "October,Groceries,Trader Joe's & Costco,315.20,Credit Card,Oats & chicken\n"
            "October,Transportation,Caltrain Monthly Pass,95.00,Clipper Card,Student pass\n"
            "October,Personal,Gym Membership,35.00,Debit Card,Campus rec pass\n"
        )
    },
    {
        "filename": "class_schedule_fall.csv",
        "type": "csv",
        "days_ago": 23,
        "tags": ["academics", "schedule"],
        "title": "Fall Semester Academic Course Timetable",
        "content": (
            "CourseCode,CourseTitle,Instructor,Days,Time,Location,Credits\n"
            "CS452,Distributed Systems Engineering,Prof. Wallace,Mon/Wed,10:00-11:30,Gates Hall 104,4\n"
            "CS421,Database System Implementation,Prof. Vance,Tue/Thu,13:00-14:30,Packard 202,4\n"
            "CS361,Machine Learning Foundations,Prof. Ng,Tue/Thu,15:00-16:30,Hewlett 200,3\n"
            "ENGR110,Engineering Ethics & Society,Prof. Miller,Friday,11:00-12:00,Thornton 110,2\n"
        )
    },
    {
        "filename": "portfolio_homepage.html",
        "type": "html",
        "days_ago": 27,
        "tags": ["portfolio", "web", "html"],
        "title": "Alex Chen Personal Developer Portfolio Webpage",
        "content": (
            "<!DOCTYPE html>\n"
            "<html lang='en'>\n"
            "<head>\n"
            "    <meta charset='UTF-8'>\n"
            "    <title>Alex Chen - Software Systems Engineer</title>\n"
            "</head>\n"
            "<body>\n"
            "    <header>\n"
            "        <h1>Alex Chen</h1>\n"
            "        <p>CS Senior passionate about low-latency systems, distributed storage, and local search algorithms.</p>\n"
            "    </header>\n"
            "    <section id='projects'>\n"
            "        <h2>Featured Engineering Projects</h2>\n"
            "        <article>\n"
            "            <h3>Compass Desktop Search Agent</h3>\n"
            "            <p>Offline desktop search combining SQLite FTS5 keyword indexing with ChromaDB semantic search.</p>\n"
            "        </article>\n"
            "    </section>\n"
            "</body>\n"
            "</html>\n"
        )
    },
    {
        "filename": "api_documentation_preview.html",
        "type": "html",
        "days_ago": 39,
        "tags": ["api", "docs", "html"],
        "title": "Internal Telemetry API Documentation Static Preview",
        "content": (
            "<!DOCTYPE html>\n"
            "<html lang='en'>\n"
            "<head>\n"
            "    <meta charset='UTF-8'>\n"
            "    <title>Compass Backend API Documentation</title>\n"
            "</head>\n"
            "<body>\n"
            "    <h1>Compass REST API Reference</h1>\n"
            "    <p>Provides local search, file indexing, recommendations, and status introspection endpoints.</p>\n"
            "    <ul>\n"
            "        <li><code>GET /api/search?query=...</code> - Query router and hybrid rank fusion</li>\n"
            "        <li><code>GET /api/index/status</code> - Live watcher metrics and progress counters</li>\n"
            "    </ul>\n"
            "</body>\n"
            "</html>\n"
        )
    }
]

SUGGESTED_QUERIES = [
    {
        "query": "kubernetes_guide.pdf",
        "expected": "kubernetes_guide.pdf",
        "strategy": "keyword",
        "description": "Exact filename search routing directly to keyword retrieval"
    },
    {
        "query": "b-trees indexing",
        "expected": "database_indexing_notes.md",
        "strategy": "keyword",
        "description": "Short 2-word technical keyword search"
    },
    {
        "query": "something about vector clocks",
        "expected": "doc4.pdf",
        "strategy": "semantic",
        "description": "Semantic query matching conceptual vector clock notes despite opaque filename"
    },
    {
        "query": "details about meal prep recipes",
        "expected": "healthy_meal_prep.txt",
        "strategy": "semantic",
        "description": "Descriptive natural language query matching culinary instructions"
    },
    {
        "query": "looking for transformer paper notes",
        "expected": "paper_summary_transformers.md",
        "strategy": "semantic",
        "description": "Concept query retrieving self-attention research paper summary"
    },
    {
        "query": "distributed key value store architecture proposal",
        "expected": "course_project_proposal.docx",
        "strategy": "hybrid",
        "description": "Multi-word hybrid search fusing keyword terms with vector similarity"
    },
    {
        "query": "spring break road trip itinerary",
        "expected": "spring_break_itinerary.pdf",
        "strategy": "hybrid",
        "description": "Multi-word query retrieving California coastal travel schedule"
    },
    {
        "query": "monthly student living expenses breakdown",
        "expected": "student_budget_2024.csv",
        "strategy": "hybrid",
        "description": "Hybrid query matching financial spreadsheet categories and amounts"
    }
]

def clean_latin1(text: str) -> str:
    replacements = {
        "\u2014": "--",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "..."
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")

def generate_pdf(filepath: str, title: str, content: str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, clean_latin1(title))
    pdf.ln(5)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, clean_latin1(content))
    pdf.output(filepath)

def generate_docx(filepath: str, title: str, content: str):
    doc = Document()
    doc.add_heading(title, level=1)
    paragraphs = content.split("\n\n")
    for p in paragraphs:
        if p.strip():
            doc.add_paragraph(p.strip())
    doc.save(filepath)

def build_sample_corpus():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest_files = []

    print(f"Building synthetic sample corpus in '{OUTPUT_DIR}'...")

    for item in DOCUMENTS:
        filename = item["filename"]
        filepath = os.path.join(OUTPUT_DIR, filename)
        file_type = item["type"]
        title = item.get("title", filename)
        content = item["content"]

        if file_type == "pdf":
            generate_pdf(filepath, title, content)
        elif file_type == "docx":
            generate_docx(filepath, title, content)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        manifest_files.append({
            "filename": filename,
            "type": file_type,
            "days_ago": item["days_ago"],
            "tags": item.get("tags", []),
            "title": title
        })
        print(f"  Created: {filename}")

    manifest_data = {
        "version": "1.0",
        "description": "Synthetic CS-student sample corpus for Compass offline demo testing.",
        "file_count": len(manifest_files),
        "files": manifest_files,
        "suggested_queries": SUGGESTED_QUERIES
    }

    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    total_size = sum(os.path.getsize(os.path.join(OUTPUT_DIR, f)) for f in os.listdir(OUTPUT_DIR) if os.path.isfile(os.path.join(OUTPUT_DIR, f)))
    print(f"\nCorpus build complete: {len(manifest_files)} files, total size: {total_size / 1024:.1f} KB (under 2MB limit).")

if __name__ == "__main__":
    build_sample_corpus()
