# Database Indexing Fundamentals: B-Trees and LSM-Trees

Database indexes are specialized auxiliary data structures designed to minimize physical disk I/O operations when retrieving records based on search key attributes.

## B-Trees and B+ Trees
B-Trees are self-balancing multi-way search trees optimized for storage systems that read and write large blocks of data. In a standard B-Tree, internal nodes store both search keys and record pointers. In a **B+ Tree**, internal nodes store only routing keys and child pointers, while all data records (or heap pointers) reside exclusively in leaf nodes.

Key advantages of B+ Trees:
- Leaf nodes are linked sequentially via pointers, making full range scans efficient without traversing parent nodes.
- Internal nodes have higher branching factor (fan-out), resulting in shallower tree height and fewer disk seeks (typically 3-4 levels).

## LSM-Trees (Log-Structured Merge-Trees)
While B+ Trees update in-place (causing random writes on disk), LSM-Trees optimize for write-heavy workloads by transforming random writes into sequential appends. Writes are buffered in memory (MemTable) and periodically flushed to immutable Sorted String Tables (SSTables).