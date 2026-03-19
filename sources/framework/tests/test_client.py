"""Tests for EngineClient."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import pytest

from source_framework.client import EngineClient


class _MockHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for testing EngineClient."""

    # Class-level state shared across requests
    last_request_path = None
    last_request_body = None
    next_response = {"id": 42}
    paused = False

    def do_GET(self):
        _MockHandler.last_request_path = self.path
        if self.path == "/engine/pipeline":
            body = json.dumps({"paused": _MockHandler.paused}).encode()
        else:
            body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        _MockHandler.last_request_path = self.path
        length = int(self.headers.get("Content-Length", 0))
        _MockHandler.last_request_body = json.loads(self.rfile.read(length)) if length else {}
        body = json.dumps(_MockHandler.next_response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress request logs


@pytest.fixture()
def mock_server():
    """Start a local HTTP server for testing."""
    server = HTTPServer(("127.0.0.1", 0), _MockHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


class TestEngineClient:
    def test_ingest_posts_to_correct_path(self, mock_server):
        client = EngineClient(mock_server, "zsh")
        _MockHandler.next_response = {"id": 99}

        row_id = client.ingest({"timestamp": "2026-01-01", "command": "ls -la"})

        assert _MockHandler.last_request_path == "/ingest/zsh"
        assert _MockHandler.last_request_body["timestamp"] == "2026-01-01"
        assert _MockHandler.last_request_body["command"] == "ls -la"
        assert row_id == 99

    def test_is_paused_false(self, mock_server):
        client = EngineClient(mock_server, "test")
        _MockHandler.paused = False
        assert not client.is_paused()

    def test_is_paused_true(self, mock_server):
        client = EngineClient(mock_server, "test")
        _MockHandler.paused = True
        assert client.is_paused()

    def test_ingest_returns_zero_on_failure(self):
        client = EngineClient("http://127.0.0.1:1", "test")  # Nothing listening
        row_id = client.ingest({"data": "x"})
        assert row_id == 0

    def test_source_name_in_path(self, mock_server):
        for name in ["screen", "audio", "oslog"]:
            client = EngineClient(mock_server, name)
            client.ingest({"test": True})
            assert _MockHandler.last_request_path == f"/ingest/{name}"
