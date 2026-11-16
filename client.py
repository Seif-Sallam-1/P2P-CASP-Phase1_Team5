import argparse
import socket
import sys

from protocol import (
    INIT,
    DATA,
    ACK,
    ERROR,
    PROTOCOL_NAME,
    pack_packet,
    unpack_packet,
    ProtocolError,
    current_timestamp_ms,
)
from logger import setup_logger

logger = setup_logger("client", "client.log")


def send_and_receive(
    sock,
    server_address,
    message_type,
    sequence_num,
    peer_id,
    payload,
):
    sent_timestamp_ms = current_timestamp_ms()
    packet = pack_packet(
        message_type, sequence_num, peer_id, payload,
        timestamp_ms=sent_timestamp_ms,
    )
    sock.sendto(packet, server_address)

    logger.info(
        "Sent message type=%s sequence=%s",
        message_type,
        sequence_num,
    )

    try:
        response, address = sock.recvfrom(2048)
    except socket.timeout:
        logger.error("Server response timeout")
        return False
    except OSError as error:
        logger.error("Socket error while waiting for response: %s", error)
        return False

    try:
        header, response_payload = unpack_packet(response)
    except ProtocolError as error:
        logger.error("Invalid server response: %s", error)
        return False

    if address != server_address:
        logger.error("Response received from unexpected address")
        return False

    if header["timestamp_ms"] != sent_timestamp_ms:
        logger.error("Response timestamp does not match request timestamp")
        return False

    rtt_ms = (current_timestamp_ms() - header["timestamp_ms"]) & 0xFFFFFFFF
    logger.info("RTT measured: %s ms", rtt_ms)

    if header["message_type"] == ERROR:
        logger.error(
            "Server returned ERROR: %s",
            response_payload.decode("utf-8", errors="replace"),
        )
        return False

    if header["message_type"] != ACK:
        logger.error("Expected ACK but received another message")
        return False

    if header["sequence_num"] != sequence_num:
        logger.error("Sequence number mismatch")
        return False

    logger.info(
        "ACK received: %s",
        response_payload.decode("utf-8", errors="replace"),
    )
    return True


def main():
    parser = argparse.ArgumentParser(description=PROTOCOL_NAME + " - UDP client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--peer-id", type=int, default=1)
    parser.add_argument("--name", default="peer-1")
    parser.add_argument("--message", default="Hello from P2P Client")
    args = parser.parse_args()

    server_address = (args.host, args.port)
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(2)

    try:
        # Phase 1 is intentionally single-shot: one send, one 2 s receive
        # window, no retransmission. Any failure yields exit status 1.
        logger.info("Starting INIT exchange")
        init_success = send_and_receive(
            client_socket,
            server_address,
            INIT,
            1,
            args.peer_id,
            args.name.encode("utf-8"),
        )

        if not init_success:
            logger.error("INIT failed. DATA will not be sent.")
            return 1

        logger.info("Starting DATA exchange")
        data_success = send_and_receive(
            client_socket,
            server_address,
            DATA,
            2,
            args.peer_id,
            args.message.encode("utf-8"),
        )

        if not data_success:
            logger.error("DATA exchange failed")
            return 1

        logger.info("Communication completed successfully")
        return 0

    finally:
        client_socket.close()
        logger.info("Client socket closed")


if __name__ == "__main__":
    sys.exit(main())
