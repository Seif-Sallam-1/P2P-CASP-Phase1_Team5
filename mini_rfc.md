# Mini-RFC: Peer-to-Peer Content-Addressable Chunk Streaming Protocol (P2P-CASP), Version 1

**Course:** CSE361 (UG2023) - Computer Networking | **Status:** Phase 1 Draft (Sections 1-3) | **Transport:** UDP

## 1. Introduction

### 1.1 Purpose

The Peer-to-Peer Content-Addressable Chunk Streaming Protocol (P2P-CASP) is an application-layer protocol for distributing a large synthetic map among a small group of peers over UDP. The map is a 64 x 64 grid split into 256 independently addressable, content-hashed chunks. The Phase 1 prototype demonstrates peer initialization (INIT) and application data exchange (DATA); the full design adds chunk availability bitmaps, explicit chunk requests, RTT/loss-aware peer selection, and recovery from peer churn.

### 1.2 Scope and Assumptions

This draft covers the protocol overview, architecture, and message formats. Assumptions: UDP only; maximum application datagram of 1200 bytes (avoids IP fragmentation); one tracker/initial seeder and at least four peers; loss, delay, and jitter introduced by Linux `tc netem`. Chunk exchange, peer monitoring, loss recovery, and completion validation are specified in later phases.

### 1.3 Terminology

- **Peer:** A client participating in map distribution.
- **Tracker:** The server component that registers peers and provides peer discovery information (also the rate-limited initial seeder in the full design).
- **Chunk:** A portion of the map distributed and verified independently.
- **INIT / DATA / ACK / ERROR:** Phase 1 message types (see Section 3.2).

### 1.4 Why a New Protocol

BitTorrent-style swarming relies on TCP and large control overhead. P2P-CASP uses a compact 15-byte UDP header, an in-header echo timestamp for continuous RTT measurement, and a flags field reserved for loss recovery, so that peer selection and reliability are decided entirely by application-layer logic under measurable network impairment.

## 2. Protocol Architecture

### 2.1 Transport

P2P-CASP runs over UDP, which is connectionless and low-overhead but provides no delivery, ordering, or duplicate guarantees. Reliability required by the complete system (retransmission, duplicate suppression, out-of-order assembly) is implemented at the application layer in later phases.

### 2.2 Components

1. **Bootstrap server / tracker:** Receives peer registrations, maintains peer address information, and supports peer discovery. In the complete design it is also a restricted initial seeder (50 kbps outbound) and the state authority for `MAP_COMPLETE`.
2. **Clients / peers:** Register with the tracker and exchange data; in the complete design they both download and upload chunks.
3. **Application protocol:** A common binary header followed by a message-specific payload.

### 2.3 Phase 1 Exchange and Finite-State Machine

1. The client creates a UDP socket (2 s receive timeout).
2. The client sends INIT with its peer name.
3. The server validates the packet, registers the peer address and ID, and replies ACK (`INIT_OK`), echoing the request timestamp.
4. The client sends DATA.
5. The server checks that the peer is registered, processes the payload, and replies ACK (`DATA_OK`).

```
Client FSM:  IDLE --send INIT--> WAIT_INIT --ACK(INIT_OK)--> REGISTERED --send DATA--> WAIT_DATA
             WAIT_DATA --ACK(DATA_OK)--> DONE (exit 0)
             WAIT_INIT/WAIT_DATA --timeout(2 s) | ERROR | invalid reply--> FAILED (exit 1)
Server FSM:  LISTEN --INIT--> LISTEN (peer registered) ; LISTEN --DATA (registered)--> LISTEN
             LISTEN --DATA (unregistered) / unknown type--> LISTEN (ERROR reply)
```

**Intentional single-shot behaviour (Phase 1):** each request is sent exactly once and the client waits a fixed 2 s for the matching ACK. There is no retransmission; a lost datagram ends in FAILED with exit status 1. Retransmission and RTO estimation are specified in Section 5 in Phase 2.

### 2.4 Planned Full-System Extensions

Peer heartbeat, chunk availability bitmap, chunk request, chunk data, and map-completion messages; hash validation, timeout/retry handling (500 ms chunk time-to-live), duplicate suppression, RTT/loss-based peer selection, and recovery from peer churn.

## 3. Message Formats

### 3.1 Common Header

Every packet begins with a fixed **15-byte** header (within the 16-byte maximum). Multi-byte integers use network byte order (big-endian). Python packing format: `struct.pack('!HBBBHHHI', ...)`, where `!` selects network byte order with no padding.

| Offset | Field | Size | Format | Description |
|---:|---|---:|:-:|---|
| 0 | Protocol_ID | 2 bytes | `H` | `0xCA51`, identifies P2P-CASP |
| 2 | Version | 1 byte | `B` | Protocol version (`1`) |
| 3 | Message_Type | 1 byte | `B` | INIT=1, DATA=2, ACK=3, ERROR=4 |
| 4 | Flags | 1 byte | `B` | Bitfield (see below) |
| 5 | Sequence_Num | 2 bytes | `H` | Request/response sequence number (0-65535) |
| 7 | Peer_ID | 2 bytes | `H` | Sender's peer identifier; server uses 0 |
| 9 | Payload_Length | 2 bytes | `H` | Payload bytes following the header |
| 11 | Timestamp | 4 bytes | `I` | 32-bit monotonic milliseconds (RTT echo) |
| | **Total** | **15 bytes** | `!HBBBHHHI` | Fixed header size |

The 16-bit sequence, peer, and payload-length fields cover 256 chunks, small swarms, and the 1200-byte datagram limit without wasting header bytes.

#### Flags bitfield (1 byte)

| Bit | Mask | Name | Meaning |
|---:|---:|---|---|
| 0 | `0x01` | RETRANSMISSION | Packet is a retransmission |
| 1 | `0x02` | PRIORITY | Packet has priority handling |
| 2 | `0x04` | FRAGMENTED | Payload belongs to a fragmented message |
| 3 | `0x08` | LAST_FRAGMENT | Payload is the final fragment |
| 4-7 | `0xF0` | Reserved | Must be zero; packets with unsupported bits are rejected |

Phase 1 INIT/DATA packets set all flags to zero; the defined bits are reserved for Phase 2 reliability and chunk transfer.

#### Timestamp and RTT echo semantics

The client writes its local monotonic time (milliseconds, `time.monotonic_ns() // 1_000_000 & 0xFFFFFFFF`) into each request. The server copies this value **unchanged** into its ACK or ERROR. The client computes `RTT = (now - echoed_timestamp) & 0xFFFFFFFF`; the echoed value must equal the one it sent, otherwise the response is discarded. The timestamp is not wall-clock time and is never compared across machines, so no clock synchronisation is needed. The counter wraps about every 49.7 days; the masked subtraction is correct across a single wrap within one exchange. In later phases the same echo mechanism feeds the per-peer RTT estimator used for peer selection.

### 3.2 Phase 1 Message Types

| Message | Type | Payload |
|---|---:|---|
| INIT | 1 | UTF-8 peer name |
| DATA | 2 | UTF-8 application data |
| ACK | 3 | UTF-8 text (`INIT_OK` or `DATA_OK`) |
| ERROR | 4 | UTF-8 error description |

### 3.3 Sample Messages (hexadecimal)

INIT from peer 1, sequence 1, payload `peer-1`, timestamp 1000 ms (21 bytes):

```
ca51 | 01 | 01 | 00 | 0001 | 0001 | 0006 | 000003e8 | 70 65 65 72 2d 31
ID     Ver  Type Flg  Seq    Peer   Len    Timestamp   "peer-1"
```

Server ACK (24 bytes): `ca51 01 03 00 0001 0000 0007 000003e8 494e49545f4f4b` (`INIT_OK`, timestamp echoed).

### 3.4 Packet Validation

A receiver MUST reject packets that are shorter than 15 bytes; exceed 1200 bytes; carry an unknown protocol ID, unsupported version, unknown message type, or unsupported flag bits; or declare a payload length that differs from the received payload size. The server additionally ignores abrupt peer disconnects (e.g. Windows `ConnectionResetError` caused by ICMP port-unreachable) and continues serving.
