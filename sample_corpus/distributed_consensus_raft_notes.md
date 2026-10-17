# Raft Consensus Protocol Overview

Raft is a consensus algorithm designed by Diego Ongaro and John Ousterhout as an understandable alternative to Multi-Paxos.

## Core Subproblems
Raft decomposes consensus into three independent subproblems:
1. **Leader Election:** When an existing leader fails or cluster initializes, a randomized election timer triggers candidate nomination.
2. **Log Replication:** The elected leader accepts client write commands, appends them to its local log, and replicates log entries to follower nodes via AppendEntries RPCs.
3. **Safety:** If any server has applied a particular log entry at a given index to its state machine, no other server may apply a different log entry for the same index.

## Election Safety and Quorums
To win an election, a candidate must gather votes from a strict majority (quorum, N/2 + 1) of cluster nodes. Randomized election timers (150ms-300ms) prevent split votes, ensuring rapid leader convergence.