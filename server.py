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
)
from logger import setup_logger

SERVER_ID = 0
logger = setup_logger("server", "server.log")


def disable_udp_connreset(sock):
    """Windows only: stop ICMP port-unreachable from aborting recvfrom()."""
    if sys.platform == "win32":
        SIO_UDP_CONNRESET = getattr(socket, "SIO_UDP_CONNRESET", 0x9800000C)
        try:
            sock.ioctl(SIO_UDP_CONNRESET, False)
        except (OSError, ValueError, AttributeError):
            pass


def send_response(
    sock, address, message_type, sequence_num, payload, request_timestamp_ms
):
    # Echo the requester timestamp so the client can calculate RTT locally.
    packet = pack_packet(
        message_type, sequence_num, SERVER_ID, payload,
        timestamp_ms=request_timestamp_ms,
    )
    sock.sendto(packet, address)


def handle_packet(sock, data, address, registered_peers):
    try:
        header, payload = unpack_packet(data)
    except ProtocolError as error:
        logger.warning("Invalid packet from %s: %s", address, error)
        return

    message_type = header["message_type"]
    sequence_num = header["sequence_num"]
    peer_id = header["peer_id"]
    request_timestamp_ms = header["timestamp_ms"]

    if message_type == INIT:
        peer_name = payload.decode("utf-8", errors="replace").strip()

        if not peer_name:
            send_response(
                sock, address, ERROR, sequence_num, b"Empty peer name",
                request_timestamp_ms
            )
            return

        registered_peers[address] = {
            "peer_id": peer_id,
            "name": peer_name,
        }

        logger.info(
            "INIT received | peer_id=%s | name=%s | address=%s",
            peer_id,
            peer_name,
            address,
        )
        send_response(
            sock, address, ACK, sequence_num, b"INIT_OK", request_timestamp_ms
        )
        logger.info("INIT ACK sent to peer %s", peer_id)

    elif message_type == DATA:
        peer = registered_peers.get(address)

        if peer is None or peer["peer_id"] != peer_id:
            send_response(
                sock, address, ERROR, sequence_num, b"Peer not registered",
                request_timestamp_ms
            )
            logger.warning("DATA rejected from unregistered peer %s", peer_id)
            return

        message = payload.decode("utf-8", errors="replace")
        logger.info(
            "DATA received | peer_id=%s | payload=%s",
            peer_id,
            message,
        )
        send_response(
            sock, address, ACK, sequence_num, b"DATA_OK", request_timestamp_ms
        )
        logger.info("DATA ACK sent to peer %s", peer_id)

    else:
        send_response(
            sock, address, ERROR, sequence_num, b"Unexpected message type",
            request_timestamp_ms
        )


def main():
    parser = argparse.ArgumentParser(description=PROTOCOL_NAME + " - UDP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    disable_udp_connreset(server_socket)
    server_socket.bind((args.host, args.port))

    registered_peers = {}
    logger.info("UDP Server listening on %s:%s", args.host, args.port)

    try:
        while True:
            try:
                data, address = server_socket.recvfrom(2048)
            except ConnectionResetError:
                # Windows reports ICMP port-unreachable from an abruptly
                # closed client as a recvfrom error; ignore and continue.
                continue
            logger.info("Packet received from %s", address)
            try:
                handle_packet(server_socket, data, address, registered_peers)
            except ConnectionResetError:
                logger.warning("Peer %s disconnected abruptly", address)
                continue

    except KeyboardInterrupt:
        logger.info("Server shutting down")

    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
