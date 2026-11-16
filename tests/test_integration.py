"""End-to-end integration tests: real server + client processes over UDP."""
import os
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.log_dir = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, CASP_LOG_DIR=self.log_dir.name,
                        PYTHONIOENCODING="utf-8")
        self.port = free_udp_port()
        self.server = None

    def tearDown(self):
        if self.server is not None:
            self.server.terminate()
            try:
                self.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server.kill()
            self.server.stdout.close()
        self.log_dir.cleanup()

    def start_server(self):
        self.server = subprocess.Popen(
            [sys.executable, "server.py", "--host", "127.0.0.1",
             "--port", str(self.port)],
            cwd=ROOT, env=self.env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
        )
        # The server logs "listening" only after bind() succeeded.
        first_line = self.server.stdout.readline()
        self.assertIn("listening", first_line, "server failed to start")

    def run_client(self, peer_id=1, timeout=15):
        return subprocess.run(
            [sys.executable, "client.py", "--host", "127.0.0.1",
             "--port", str(self.port), "--peer-id", str(peer_id),
             "--name", f"it-peer-{peer_id}",
             "--message", "integration DATA payload"],
            cwd=ROOT, env=self.env, capture_output=True, text=True,
            timeout=timeout,
        )

    def test_init_and_data_exchange(self):
        self.start_server()
        result = self.run_client(peer_id=7)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("INIT_OK", result.stdout)
        self.assertIn("DATA_OK", result.stdout)
        self.assertIn("RTT measured", result.stdout)
        self.assertIn("Communication completed successfully", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_client_exits_nonzero_when_server_absent(self):
        # No server started: INIT times out (single-shot, 2 s) -> exit 1.
        result = self.run_client(peer_id=9)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("INIT failed", result.stdout)


if __name__ == "__main__":
    unittest.main()
