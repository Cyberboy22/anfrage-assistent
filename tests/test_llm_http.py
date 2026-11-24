"""Prüft die echte HTTP-Anbindung an Ollama gegen einen kleinen Test-Server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from assistent.llm import KIEinstellungen, KIFehler, frage_ki, ollama_modelle


class FakeOllama(BaseHTTPRequestHandler):
    anfragen: list = []

    def log_message(self, *args):
        pass

    def _send(self, code, daten):
        body = json.dumps(daten).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"models": [{"name": "llama3.2:latest"}]})

    def do_POST(self):
        daten = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.anfragen.append(daten)
        if daten["model"] == "fehlt":
            return self._send(404, {"error": "model not found"})
        self._send(200, {"message": {"role": "assistant", "content": '{"baujahr": 1990}'}})


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_ollama_anfrage(server):
    einst = KIEinstellungen("ollama", modell="llama3.2", ollama_url=server)
    antwort = frage_ki(einst, "system", "nutzer", {"type": "object"})
    assert json.loads(antwort) == {"baujahr": 1990}
    gesendet = FakeOllama.anfragen[-1]
    assert gesendet["stream"] is False
    assert gesendet["format"] == {"type": "object"}
    assert gesendet["messages"][0]["role"] == "system"


def test_ollama_modelle(server):
    assert ollama_modelle(server) == ["llama3.2:latest"]


def test_modell_fehlt(server):
    with pytest.raises(KIFehler, match="ollama pull fehlt"):
        frage_ki(KIEinstellungen("ollama", modell="fehlt", ollama_url=server), "s", "n")


def test_ollama_aus():
    assert ollama_modelle("http://127.0.0.1:9") is None
    with pytest.raises(KIFehler, match="nicht erreichbar"):
        frage_ki(KIEinstellungen("ollama", ollama_url="http://127.0.0.1:9"), "s", "n")


def test_api_ohne_schluessel():
    with pytest.raises(KIFehler, match="API-Schlüssel"):
        frage_ki(KIEinstellungen("claude"), "s", "n")
