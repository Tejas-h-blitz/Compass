# TCP/IP Transport Layer Architecture

Transmission Control Protocol (TCP) provides a reliable, ordered, and error-checked stream of octets over an unreliable packet network (IP).

## Three-Way Handshake
1. Client -> Server: `SYN` (Sequence Number = X)
2. Server -> Client: `SYN-ACK` (Sequence Number = Y, Acknowledgment Number = X + 1)
3. Client -> Server: `ACK` (Acknowledgment Number = Y + 1)

## Flow Control vs Congestion Control
- **Flow Control:** Prevents the sender from overwhelming the receiver's buffer. The receiver advertises its available buffer space via the `Receive Window (rwnd)` header field.
- **Congestion Control:** Prevents senders from overwhelming the intermediate network infrastructure. Uses Slow Start, Congestion Avoidance (AIMD - Additive Increase Multiplicative Decrease), Fast Retransmit, and Fast Recovery algorithms.