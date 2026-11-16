# Project Proposal: Peer-to-Peer Content-Addressable Chunk Streaming Protocol

**Course:** CSE361 (UG2023) - Computer Networking  
**Protocol:** Peer-to-Peer Content-Addressable Chunk Streaming Protocol (P2P-CASP), Version 1  
**Project:** Project 1 - Decentralized Cartographer | **Phase:** 1 (Prototype)

**Team Members:**

- Tasneem Mohamed Shaban Nasr (24P0443)
- Ahmed Tamer Ahmed Abdelhalim (24P0189)
- Mazen Hesham Ibrahim Shahbunder (24P0432)
- Seif Emad Eldin Sallam (24P0386)
- Sama Tarek Mostafa (23P0451)

## 1. Problem Statement

Distributing a large shared object (here a 64 x 64 map of 256 chunks) from one server to many clients does not scale if the server alone supplies every byte. The assignment caps the server at 50 kbps outbound, so clients must obtain most chunks from each other. Doing this over UDP, which gives no delivery, ordering, or duplicate guarantees, requires an application-layer protocol that (a) advertises which chunks each peer holds, (b) requests chunks explicitly and in parallel, (c) measures per-peer RTT and loss to pick the best source, and (d) tolerates loss, reordering, duplicates, and peers that disappear mid-transfer. Our goal is a compact, original protocol that satisfies these needs and can be measured under `tc netem` impairment (5% loss, 100 ms delay with 20 ms jitter, and peer churn).

## 2. Protocol Architecture

The system has one **tracker / restricted seeder** (server) and at least four **peers** (clients), all communicating over UDP with datagrams of at most 1200 bytes.

- **Tracker:** registry of active peers (INIT), peer list distribution, initial chunk seeding throttled to 50 kbps, and `MAP_COMPLETE` validation.
- **Peers:** register, exchange `CHUNK_BITMAP` advertisements, send `CHUNK_REQ`, serve `CHUNK_DATA`, and exchange `PEER_HEARTBEAT` for RTT measurement.
- **Phase 1 flow (implemented):** INIT -> ACK(`INIT_OK`) -> DATA -> ACK(`DATA_OK`), single-shot with a 2 s timeout and no retransmission; the client exits 1 on failure.

```
 Peer 1 ----\                      /---- Peer 3
 Peer 2 -----+--> Tracker/Seeder <-+---- Peer 4      (INIT, bitmaps, 50 kbps seeding)
      \_________ peer-to-peer CHUNK_REQ / CHUNK_DATA _________/
```

## 3. Header Design and Custom-Field Justification

Fixed **15-byte** header, big-endian, struct format `!HBBBHHHI` (limit: 16 bytes).

| Offset | Field | Size | Rationale |
|---:|---|---:|---|
| 0 | Protocol_ID | 2 B | `0xCA51` rejects foreign traffic cheaply |
| 2 | Version | 1 B | Allows protocol evolution |
| 3 | Message_Type | 1 B | 256 possible types; INIT, DATA, ACK, ERROR now, heartbeat/bitmap/request/chunk later |
| 4 | Flags | 1 B | **Custom:** RETRANSMISSION, PRIORITY, FRAGMENTED, LAST_FRAGMENT |
| 5 | Sequence_Num | 2 B | Matches responses; 65,536 values far exceed 256 chunks |
| 7 | Peer_ID | 2 B | Identifies up to 65,536 peers; server is 0 |
| 9 | Payload_Length | 2 B | Integrity check against the 1200-byte limit |
| 11 | Timestamp | 4 B | **Custom:** monotonic-ms RTT echo |

**Original mechanism 1 - in-header echo timestamp.** The sender stamps a 32-bit monotonic millisecond value; the responder echoes it unchanged. The sender computes `RTT = (now - echo) mod 2^32`. No clock synchronisation or separate probe packets are needed, and every request/response pair yields an RTT sample for the per-peer estimator. A mismatched echo is discarded, which also rejects stale replies.

**Original mechanism 2 - Flags bitfield.** RETRANSMISSION lets receivers and logs distinguish retries from first transmissions (duplicate-chunk accounting); FRAGMENTED/LAST_FRAGMENT allow multi-datagram payloads; PRIORITY marks urgent chunk requests. Reserved bits must be zero and are rejected.

**Planned original mechanism 3 - compact bitmap.** `CHUNK_BITMAP` carries the 256-chunk availability set as a 32-byte raw bitmap, switching to run-length ranges when sparse or nearly full, to keep signaling overhead low.

**Difference from known protocols:** unlike BitTorrent (TCP, large handshake, variable-length messages) and MQTT-SN (broker pub/sub), P2P-CASP is UDP-native with a fixed 15-byte header, a per-packet RTT echo, and tracker-throttled seeding; no external networking libraries are used.

## 4. Roadmap

**Phase 1 - Prototype (Week 7).** Header encode/decode/validation; INIT and DATA exchange; 4-concurrent-client baseline scripts for Linux and Windows; unit and integration tests; logs and loopback pcap; proposal, Mini-RFC sections 1-3, README and demo video.

**Phase 2 - Features and tests (Week 12).**
- *Chunking:* deterministic seeded pseudo-random generator; 256 chunks; SHA-256 content hash per chunk (truncated in headers/bitmaps as needed); payload <= 1200 bytes including header.
- *Bitmap:* `CHUNK_BITMAP` advertisements, incremental updates after each verified chunk.
- *Requests and reliability:* parallel `CHUNK_REQ`, 500 ms time-to-live then re-request from another peer, out-of-order assembly, duplicate suppression, RTO from smoothed RTT (`RTO = SRTT + 4 * RTTVAR`).
- *Peer selection:* score = f(smoothed RTT, loss rate) from heartbeats and chunk responses.
- *Peer churn:* heartbeat timeout marks a peer dead, its bitmap entries are dropped, outstanding requests are rerouted; no deadlock when Client 2 is killed at 50%.
- *Server:* token-bucket 50 kbps throttle, peer registry, `MAP_COMPLETE` validation.

**Phase 3 - Final (Week 14).** Final Mini-RFC (5-8 pages), technical report with plots (completion time vs loss rate, p2p transfer ratio), slides, final demo video, full commit history.

## 5. Testing Strategy

Linux is the grading platform; all impairments use `tc qdisc ... netem` applied and removed by `run_experiments.sh`, with fixed random seeds and at least five repetitions per scenario (min/median/max reported).

| Scenario | Impairment | Acceptance criterion |
|---|---|---|
| Baseline (LAN) | none | 4 clients 100% complete in < 5 s; server <= 50 kbps |
| Moderate loss | `loss 5%` | complete without corruption; duplicates <= 2% |
| Asymmetric delay | `delay 100ms 20ms` on clients 1, 2 | clients 3, 4 serve > 75% of P2P transfers |
| Peer churn | kill client 2 at 50% | survivors time out, update bitmaps, finish |

**Metrics:** `completion_time_ms`, `p2p_transfer_ratio`, `duplicate_chunk_count`, `signaling_overhead`, `mean_rtt_per_peer`. **Evidence:** timestamped sent/received packet logs, CSV outputs, plots, and `.pcap` files (two runs per scenario). Phase 1 evidence: `run_baseline.sh` / `run_baseline.ps1` (4 concurrent clients, non-zero exit on any failure), unit and integration tests, and a loopback capture of the baseline run.
