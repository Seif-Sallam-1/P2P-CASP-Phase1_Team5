import struct
import time


PROTOCOL_NAME = "Peer-to-Peer Content-Addressable Chunk Streaming Protocol"
PROTOCOL_ABBREVIATION = "P2P-CASP"
PROTOCOL_FULL_NAME = PROTOCOL_NAME  # backwards-compatible alias

PROTOCOL_ID = 0xCA51
VERSION = 1

INIT = 1
DATA = 2
ACK = 3
ERROR = 4

# Header fields total 15 bytes (within the assignment's 16-byte maximum):
# Protocol ID(2), Version(1), Message Type(1), Flags(1),
# Sequence Number(2), Peer ID(2), Payload Length(2), Timestamp(4).
HEADER_FORMAT = "!HBBBHHHI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_DATAGRAM_SIZE = 1200

# One-byte flag bitfield.
FLAG_RETRANSMISSION = 0x01
FLAG_PRIORITY = 0x02
FLAG_FRAGMENTED = 0x04
FLAG_LAST_FRAGMENT = 0x08
VALID_FLAGS_MASK = (
    FLAG_RETRANSMISSION | FLAG_PRIORITY | FLAG_FRAGMENTED | FLAG_LAST_FRAGMENT
)

VALID_MESSAGE_TYPES = {INIT, DATA, ACK, ERROR}


class ProtocolError(Exception):
    """Raised when a received packet does not follow the protocol."""


def current_timestamp_ms():
    """Return a wrap-safe 32-bit monotonic timestamp in milliseconds."""
    return (time.monotonic_ns() // 1_000_000) & 0xFFFFFFFF


def pack_packet(
    message_type,
    sequence_num,
    peer_id,
    payload=b"",
    flags=0,
    timestamp_ms=None,
):
    if message_type not in VALID_MESSAGE_TYPES:
        raise ProtocolError("Invalid message type")

    if not isinstance(payload, bytes):
        raise ProtocolError("Payload must be bytes")

    if not (0 <= flags <= 0xFF) or (flags & ~VALID_FLAGS_MASK):
        raise ProtocolError("Flags contain unsupported bits")

    if not (0 <= sequence_num <= 0xFFFF):
        raise ProtocolError("Sequence number is out of range (0..65535)")

    if not (0 <= peer_id <= 0xFFFF):
        raise ProtocolError("Peer ID is out of range (0..65535)")

    if timestamp_ms is None:
        timestamp_ms = current_timestamp_ms()
    if not (0 <= timestamp_ms <= 0xFFFFFFFF):
        raise ProtocolError("Timestamp is out of range")

    if HEADER_SIZE + len(payload) > MAX_DATAGRAM_SIZE:
        raise ProtocolError("Packet exceeds maximum datagram size")

    header = struct.pack(
        HEADER_FORMAT,
        PROTOCOL_ID,
        VERSION,
        message_type,
        flags,
        sequence_num,
        peer_id,
        len(payload),
        timestamp_ms,
    )
    return header + payload


def unpack_packet(data):
    if len(data) < HEADER_SIZE:
        raise ProtocolError("Packet is smaller than the header")

    if len(data) > MAX_DATAGRAM_SIZE:
        raise ProtocolError("Packet exceeds maximum datagram size")

    (
        protocol_id,
        version,
        message_type,
        flags,
        sequence_num,
        peer_id,
        payload_length,
        timestamp_ms,
    ) = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])

    if protocol_id != PROTOCOL_ID:
        raise ProtocolError("Unknown protocol ID")

    if version != VERSION:
        raise ProtocolError("Unsupported protocol version")

    if message_type not in VALID_MESSAGE_TYPES:
        raise ProtocolError("Unknown message type")

    if flags & ~VALID_FLAGS_MASK:
        raise ProtocolError("Packet contains unsupported flag bits")

    payload = data[HEADER_SIZE:]

    if len(payload) != payload_length:
        raise ProtocolError("Payload length mismatch")

    header = {
        "protocol_id": protocol_id,
        "version": version,
        "message_type": message_type,
        "flags": flags,
        "sequence_num": sequence_num,
        "peer_id": peer_id,
        "payload_length": payload_length,
        "timestamp_ms": timestamp_ms,
    }
    return header, payload
