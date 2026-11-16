# P2P-CASP — Phase 1

Protocol Name: Peer-to-Peer Content-Addressable Chunk Streaming Protocol (P2P-CASP)

## Demo video

**Demo video URL (access: Anyone with the link can view):** https://drive.google.com/drive/folders/11yZikGXSIVaNirTm7sGsPmatvrSrlBP9 

## Requirements

- Python 3.10 or later
- Windows, Linux, or Kali Linux
- No third-party Python packages are required

## Project files

- `protocol.py`: 15-byte binary header (Flags + Timestamp), encoding, decoding, and validation
- `server.py`: UDP server / initial tracker prototype
- `client.py`: UDP client demonstrating INIT and DATA
- `logger.py`: console and file logging
- `tests/test_protocol.py`: protocol unit tests
- `tests/test_end_to_end.py`: end-to-end test (real server + real clients)
- `run_baseline.sh` / `run_baseline.ps1`: four-peer automated baseline tests for Linux and Windows
- `mini_rfc.md`: Mini-RFC draft, Sections 1–3
- `HOW_TO_RUN_WINDOWS.txt`: Windows PowerShell instructions
- `HOW_TO_RUN_LINUX.txt`: Linux/Kali instructions

## Setup

No setup is needed: the prototype uses only the Python standard library, so there is nothing to `pip install` and a virtual environment is **optional**. The baseline scripts use `venv/` if you created one, otherwise the system Python (`python3` on Linux, `py -3`/`python` on Windows).

If you prefer a venv:

```powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
```

```bash
python3 -m venv venv
source venv/bin/activate
```

Step-by-step guides are in `HOW_TO_RUN_WINDOWS.txt` and `HOW_TO_RUN_LINUX.txt`.

## Run the server

Open a terminal in the project folder.

Windows PowerShell:

```powershell
python server.py --host 127.0.0.1 --port 5000
```

Linux / Kali Linux:

```bash
python3 server.py --host 127.0.0.1 --port 5000
```

## Run a client

Open a second terminal in the project folder.

Windows PowerShell:

```powershell
python client.py --host 127.0.0.1 --port 5000
```

Linux / Kali Linux:

```bash
python3 client.py --host 127.0.0.1 --port 5000
```

Expected output includes `INIT_OK`, `DATA_OK`, and an `RTT measured` line. The server echoes the 32-bit monotonic timestamp from the client, allowing the client to calculate round-trip time without comparing clocks between machines.

## Run unit tests

Windows PowerShell:

```powershell
python -m unittest discover -s tests -v
```

Linux / Kali Linux:

```bash
python3 -m unittest discover -s tests -v
```

## Run the automated baseline test

Windows PowerShell:

```powershell
.\run_baseline.ps1
```

Linux / Kali Linux:

```bash
chmod +x run_baseline.sh
./run_baseline.sh
```

Both scripts behave identically: they run the unit tests (including the end-to-end test), start a temporary server on port 5001, run four separate clients **one after another**, verify INIT/DATA/RTT success for each peer, check that the server logged 4 INIT and 4 DATA messages, and stop the server. Client processes exit with code 0 on success and 1 on failure, and the scripts check that exit code. This is a four-peer sequential smoke test, not a concurrent transfer test.

## Logs

Logs are written under `logs/` and are kept as Phase 1 evidence. The baseline scripts create:

- `logs/baseline_server.log`
- `logs/baseline_client_1.log` ... `logs/baseline_client_4.log` (one per client)

Logs are written directly by the programs (UTF-8, `--log-file` option), and the console handler uses stdout, so no shell redirection is needed.

## Phase 1 scope

This prototype demonstrates the INIT and DATA message exchanges over UDP. It does not yet implement full chunk-based P2P distribution, peer heartbeat, chunk bitmaps, chunk requests, network impairment scenarios, or the 50 kbps aggregate server throttle. Those belong to later implementation phases.

Retransmission is intentionally not implemented in Phase 1: the client sends each message once, waits 2 seconds for the reply, and exits with a non-zero status if none arrives. Loss recovery (timeouts, retransmission using `FLAG_RETRANSMISSION`) is planned for later phases.

The server tolerates peers that disappear: on Windows it disables the UDP "connection reset" error (`SIO_UDP_CONNRESET`) and also ignores `ConnectionResetError`, so a hard-killed client cannot crash it.
