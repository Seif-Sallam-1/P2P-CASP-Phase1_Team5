import struct
import unittest

from protocol import (
    PROTOCOL_ID,
    VERSION,
    HEADER_SIZE,
    HEADER_FORMAT,
    DATA,
    FLAG_PRIORITY,
    FLAG_RETRANSMISSION,
    pack_packet,
    unpack_packet,
    ProtocolError,
)


class ProtocolTests(unittest.TestCase):
    def test_header_size_is_within_16_byte_limit(self):
        self.assertEqual(HEADER_SIZE, 15)
        self.assertLessEqual(HEADER_SIZE, 16)

    def test_packet_round_trip(self):
        packet = pack_packet(
            DATA, 10, 3, b"Hello", flags=FLAG_PRIORITY, timestamp_ms=123456
        )
        header, payload = unpack_packet(packet)

        self.assertEqual(header["protocol_id"], PROTOCOL_ID)
        self.assertEqual(header["version"], VERSION)
        self.assertEqual(header["message_type"], DATA)
        self.assertEqual(header["flags"], FLAG_PRIORITY)
        self.assertEqual(header["sequence_num"], 10)
        self.assertEqual(header["peer_id"], 3)
        self.assertEqual(header["payload_length"], 5)
        self.assertEqual(header["timestamp_ms"], 123456)
        self.assertEqual(payload, b"Hello")

    def test_default_timestamp_is_added(self):
        packet = pack_packet(DATA, 1, 1, b"x")
        header, _ = unpack_packet(packet)
        self.assertIsInstance(header["timestamp_ms"], int)
        self.assertGreaterEqual(header["timestamp_ms"], 0)

    def test_flags_round_trip(self):
        packet = pack_packet(DATA, 1, 1, b"x", flags=FLAG_RETRANSMISSION)
        header, _ = unpack_packet(packet)
        self.assertEqual(header["flags"], FLAG_RETRANSMISSION)

    def test_reject_unsupported_flags(self):
        with self.assertRaises(ProtocolError):
            pack_packet(DATA, 1, 1, b"x", flags=0x80)

    def test_reject_sequence_number_overflow(self):
        with self.assertRaises(ProtocolError):
            pack_packet(DATA, 0x10000, 1, b"")

    def test_reject_peer_id_overflow(self):
        with self.assertRaises(ProtocolError):
            pack_packet(DATA, 1, 0x10000, b"")

    def test_reject_timestamp_overflow(self):
        with self.assertRaises(ProtocolError):
            pack_packet(DATA, 1, 1, b"", timestamp_ms=0x100000000)

    def test_reject_short_packet(self):
        with self.assertRaises(ProtocolError):
            unpack_packet(b"short")

    def test_reject_wrong_payload_length(self):
        header = struct.pack(
            HEADER_FORMAT, PROTOCOL_ID, VERSION, DATA, 0, 1, 3, 10, 123
        )
        with self.assertRaises(ProtocolError):
            unpack_packet(header + b"Hello")

    def test_reject_invalid_protocol_id(self):
        header = struct.pack(
            HEADER_FORMAT, 1234, VERSION, DATA, 0, 1, 3, 0, 123
        )
        with self.assertRaises(ProtocolError):
            unpack_packet(header)

    def test_reject_oversized_packet(self):
        with self.assertRaises(ProtocolError):
            pack_packet(DATA, 1, 1, b"A" * 1200)


if __name__ == "__main__":
    unittest.main()
