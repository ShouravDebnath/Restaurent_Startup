"""A single-client TCP RTSP gate: one configured upstream IP, no redirects or UDP.

Native decoders see only the private loopback gateway. RTSP/SDP authorities are
validated/replaced before reaching FFmpeg; credentials are injected upstream only.
This is a deliberately narrow compatibility profile, not a general NVR proxy.
"""

import base64
import contextlib
import hashlib
import re
import secrets
import socket
import threading
from urllib.parse import urlsplit
from urllib.request import parse_http_list, parse_keqv_list

from restaurant_edge.secret_store import read as read_credential
from restaurant_edge.video_sources import SourceFailure


def packet(stream):
    first = stream.read(1)
    if not first:
        raise EOFError
    if first == b"$":
        header = stream.read(3)
        if len(header) != 3:
            raise EOFError
        size = int.from_bytes(header[1:], "big")
        body = stream.read(size)
        if len(body) != size:
            raise EOFError
        return first + header + body
    header = bytearray(first)
    while not header.endswith(b"\r\n\r\n"):
        if len(header) > 32768:
            raise SourceFailure("RTSP_RESPONSE_LIMIT")
        char = stream.read(1)
        if not char:
            raise EOFError
        header += char
    size_match = re.search(rb"(?im)^content-length:\s*(\d+)", header)
    size = int(size_match[1]) if size_match else 0
    if size > 1_000_000:
        raise SourceFailure("RTSP_RESPONSE_LIMIT")
    body = stream.read(size)
    if len(body) != size:
        raise EOFError
    return bytes(header) + body


def rewrite_response(data, upstream, local):
    if data.startswith(b"$"):
        return data
    header, body = data.split(b"\r\n\r\n", 1)
    if not re.match(rb"RTSP/1\.0 2\d\d\b", header):
        raise SourceFailure("RTSP_RESPONSE_REJECTED")
    text = (header + b"\r\n\r\n" + body).decode("latin1")
    expected = urlsplit(upstream)
    for match in re.finditer(r"(?i)[a-z][a-z0-9+.-]*://[^\s\r\n]+", text):
        parsed = urlsplit(match[0])
        if parsed.scheme.lower() != "rtsp" or parsed.hostname != expected.hostname or (
                parsed.port or 554) != (expected.port or 554) or parsed.username or parsed.password:
            raise SourceFailure("DESTINATION_REJECTED")
    # The decoder is allowed only TCP RTSP through this loopback relay.
    if re.search(rb"(?im)^Transport:", header) and not re.search(rb"(?im)^Transport:.*RTP/AVP/TCP", header):
        raise SourceFailure("DESTINATION_REJECTED")
    # Canonicalize every validated authority, including an omitted default port.
    # A literal string replacement misses rtsp://host when configured host:554.
    def replace_uri(match):
        parsed = urlsplit(match[0])
        return local + parsed.path + ("?" + parsed.query if parsed.query else "")

    rewritten = re.sub(r"(?i)[a-z][a-z0-9+.-]*://[^\s\r\n]+", replace_uri, text).encode("latin1")
    new_header, new_body = rewritten.split(b"\r\n\r\n", 1)
    if re.search(rb"(?im)^Content-Type:\s*application/sdp", new_header) or new_body.startswith(b"v=0\r\n"):
        # Do not advertise audio/data tracks to the decoder at all.
        retained, include, video = [], True, False
        for line in new_body.splitlines(keepends=True):
            if line.startswith(b"m="):
                include = line.startswith(b"m=video ")
                video |= include
            if include:
                retained.append(line)
        if not video:
            raise SourceFailure("VIDEO_TRACK_UNAVAILABLE")
        new_body = b"".join(retained)
    if b"Content-Length:" in new_header or b"content-length:" in new_header.lower():
        new_header = re.sub(rb"(?im)^(Content-Length:)\s*\d+", lambda m: m[1] + b" " + str(len(new_body)).encode(), new_header)
    return new_header + b"\r\n\r\n" + new_body


def authorization(challenge, credential, method, uri):
    if challenge.startswith("Basic "):
        token = base64.b64encode((credential.username + ":" + credential.password).encode()).decode()
        return "Basic " + token
    if not challenge.startswith("Digest "):
        raise SourceFailure("CAMERA_AUTHORIZATION_FAILED")
    params = parse_keqv_list(parse_http_list(challenge[7:]))
    algorithm = params.get("algorithm", "MD5").upper()
    if algorithm not in {"MD5", "SHA-256"} or any('"' in x or '\r' in x or '\n' in x
            for x in [credential.username, *params.values()]):
        raise SourceFailure("CAMERA_AUTHORIZATION_FAILED")
    def hashed(value):
        return hashlib.new("md5" if algorithm == "MD5" else "sha256", value.encode()).hexdigest()
    realm, nonce = params.get("realm", ""), params.get("nonce", "")
    cnonce, nc = secrets.token_hex(12), "00000001"
    a1, a2 = hashed(f"{credential.username}:{realm}:{credential.password}"), hashed(f"{method}:{uri}")
    qop = params.get("qop")
    if qop and "auth" not in [v.strip() for v in qop.split(",")]:
        raise SourceFailure("CAMERA_AUTHORIZATION_FAILED")
    response = hashed(f"{a1}:{nonce}:{nc}:{cnonce}:auth:{a2}" if qop else f"{a1}:{nonce}:{a2}")
    result = f'Digest username="{credential.username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}", algorithm={algorithm}'
    if qop:
        result += f', qop=auth, nc={nc}, cnonce="{cnonce}"'
    if "opaque" in params:
        result += f', opaque="{params["opaque"]}"'
    return result


class RestrictedRTSPGateway:
    def __init__(self, source):
        self.source = source
        host = f"[{source.host}]" if ":" in source.host else source.host
        self.upstream = f"rtsp://{host}:{source.port}"
        self.remote = self.listener = self.client = None
        self.closed = threading.Event()
        self.thread = None
        self.challenge = None
        self.credential = None

    def start(self):
        try:
            self.credential = read_credential(self.source)
        except Exception:  # noqa: BLE001 - secret-store/native boundary reports only a fixed reason
            raise SourceFailure("CAMERA_CREDENTIAL_UNAVAILABLE") from None
        try:
            # SourceDefinition accepts a literal private LAN IP, so no DNS resolution/redirect choice.
            self.remote = socket.create_connection((self.source.host, self.source.port), timeout=5)
            self.remote.settimeout(6)
            self.reader = self.remote.makefile("rb")
            uri = self.upstream + self.source.stream_path
            probe = f"DESCRIBE {uri} RTSP/1.0\r\nCSeq: 0\r\nAccept: application/sdp\r\n\r\n"
            self.remote.sendall(probe.encode())
            initial = packet(self.reader)
            if initial.startswith(b"RTSP/1.0 401"):
                match = re.search(rb"(?im)^WWW-Authenticate:\s*([^\r\n]+)", initial)
                if not match or not self.credential.username:
                    raise SourceFailure("CAMERA_AUTHORIZATION_FAILED")
                self.challenge = match[1].decode("latin1")
                auth = authorization(self.challenge, self.credential, "DESCRIBE", uri)
                self.remote.sendall(probe.replace("CSeq: 0", "CSeq: 1").replace("\r\n\r\n", "\r\nAuthorization: " + auth + "\r\n\r\n").encode())
                initial = packet(self.reader)
                if initial.startswith(b"RTSP/1.0 401"):
                    raise SourceFailure("CAMERA_AUTHORIZATION_FAILED")
            # Check SDP/redirect policy before permitting a native decoder to open anything.
            rewrite_response(initial, self.upstream, self.upstream)
            self.listener = socket.socket()
            self.listener.bind(("127.0.0.1", 0))
            self.listener.listen(1)
            self.listener.settimeout(5)
            self.local = f"rtsp://127.0.0.1:{self.listener.getsockname()[1]}"
            self.thread = threading.Thread(target=self._serve, daemon=True)
            self.thread.start()
            return self.local + self.source.stream_path
        except SourceFailure:
            self.close()
            raise
        except (OSError, EOFError, ValueError):
            self.close()
            raise SourceFailure("RTSP_CONNECTION_FAILED") from None

    def _serve(self):
        try:
            self.client, _ = self.listener.accept()
            self.client.settimeout(6)
            self.listener.close()
            self.listener = None
            forwarding = threading.Thread(target=self._upstream_requests, daemon=True)
            forwarding.start()
            while not self.closed.is_set():
                data = packet(self.reader)
                self.client.sendall(rewrite_response(data, self.upstream, self.local))
        except (OSError, EOFError, ValueError, SourceFailure):
            pass
        finally:
            self.close()

    def _upstream_requests(self):
        try:
            with self.client.makefile("rb") as incoming:
                while not self.closed.is_set():
                    data = packet(incoming)
                    if data.startswith(b"$"):
                        self.remote.sendall(data)
                        continue
                    header, body = data.split(b"\r\n\r\n", 1)
                    lines = header.decode("latin1").split("\r\n")
                    method, uri, protocol = lines[0].split(" ")
                    if method not in {"OPTIONS", "DESCRIBE", "SETUP", "PLAY", "PAUSE", "TEARDOWN", "GET_PARAMETER", "SET_PARAMETER"}:
                        raise SourceFailure("DESTINATION_REJECTED")
                    target = urlsplit(uri)
                    if target.netloc != urlsplit(self.local).netloc or protocol != "RTSP/1.0":
                        raise SourceFailure("DESTINATION_REJECTED")
                    if method == "SETUP" and not re.search(r"(?im)^Transport:.*RTP/AVP/TCP", header.decode("latin1")):
                        raise SourceFailure("DESTINATION_REJECTED")
                    uri = self.upstream + target.path + ("?" + target.query if target.query else "")
                    lines = [f"{method} {uri} RTSP/1.0"] + [line for line in lines[1:] if not line.lower().startswith("authorization:")]
                    if self.challenge:
                        lines.append("Authorization: " + authorization(self.challenge, self.credential, method, uri))
                    self.remote.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin1") + body)
        except (OSError, EOFError, ValueError, SourceFailure):
            self.close()

    def close(self):
        self.closed.set()
        for name in ("remote", "client", "listener"):
            sock = getattr(self, name)
            if sock:
                with contextlib.suppress(OSError):
                    sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                setattr(self, name, None)
        if hasattr(self, "reader"):
            with contextlib.suppress(OSError):
                self.reader.close()
