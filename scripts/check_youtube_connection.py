#!/usr/bin/env python3
"""One-time local YouTube OAuth check. No publishing, saved tokens, or extra packages."""
import argparse
import base64
import hashlib
import html
import json
import secrets
import ssl
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
REDIRECT = "http://localhost:8789/oauth/callback"
AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
REVOKE = "https://oauth2.googleapis.com/revoke"
try:
    import certifi
except ImportError:
    TLS_CONTEXT = ssl.create_default_context()
else:
    TLS_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def load_client(path):
    config = json.loads(Path(path).read_text())["web"]
    if REDIRECT not in config.get("redirect_uris", []):
        raise ValueError("OAuth client must allow " + REDIRECT)
    if not config.get("client_id") or not config.get("client_secret"):
        raise ValueError("Client ID and secret are required")
    return config


def post_form(url, values):
    request = urllib.request.Request(url, urllib.parse.urlencode(values).encode(),
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=30, context=TLS_CONTEXT) as response:
        body = response.read()
        return json.loads(body) if body else {}


class Probe(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, client, output):
        self.client = client
        self.lock = threading.Lock()
        self.output = Path(output)
        self.state = None
        self.verifier = None
        self.done = False
        self.last_message = "Проверка ещё не запускалась."
        self.deadline = time.monotonic() + 900
        super().__init__(("127.0.0.1", 8789), Handler)
        self.timeout = 1

    def authorization_url(self):
        self.state = secrets.token_urlsafe(32)
        self.verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b"=").decode()
        return AUTH + "?" + urllib.parse.urlencode({
            "client_id": self.client["client_id"], "redirect_uri": REDIRECT,
            "response_type": "code", "scope": SCOPE, "state": self.state,
            "code_challenge": challenge, "code_challenge_method": "S256",
            "access_type": "online", "prompt": "consent select_account",
        })

    def inspect_channel(self, code, verifier):
        token = post_form(TOKEN, {"client_id": self.client["client_id"],
            "client_secret": self.client["client_secret"], "code": code,
            "code_verifier": verifier, "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
        access = token["access_token"]
        try:
            if SCOPE not in token.get("scope", "").split():
                raise ValueError("Read-only permission was not granted")
            request = urllib.request.Request(
                "https://www.googleapis.com/youtube/v3/channels?part=id,snippet&mine=true",
                headers={"Authorization": "Bearer " + access})
            with urllib.request.urlopen(request, timeout=30, context=TLS_CONTEXT) as response:
                data = json.load(response)
            channels = [{"id": item["id"], "title": item["snippet"]["title"],
                         "handle": item["snippet"].get("customUrl"),
                         "url": "https://www.youtube.com/channel/" + item["id"]}
                        for item in data.get("items", [])]
            result = {"checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "scope": SCOPE, "channels": channels,
                      "api_read_ok": True, "upload_tested": False}
        finally:
            # This is a disposable check, not the future Postiz authorization.
            try:
                post_form(REVOKE, {"token": access})
                revoked = True
            except (urllib.error.URLError, ValueError):
                revoked = False
            access = None
            token.clear()
        result["test_access_revoked"] = revoked
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        self.output.chmod(0o600)
        return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # OAuth callback URLs must never reach terminal/access logs.

    def page(self, message, status=200):
        body = ("<!doctype html><meta charset=utf-8><meta name=referrer content=no-referrer>"
                "<title>Проверка YouTube</title><style>body{max-width:740px;margin:64px auto;"
                "font:18px/1.6 system-ui;padding:24px}a{color:#145bc7}</style>" + message).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get("Host") not in {"localhost:8789", "127.0.0.1:8789"}:
            return self.page("Недопустимый адрес.", 400)
        path = urllib.parse.urlsplit(self.path)
        if path.path == "/":
            return self.page("<h1>Проверка доступа к YouTube</h1><p>Только чтение названия и ID канала. "
                "Без загрузки, публикации и удаления видео. После запроса тестовый доступ будет отозван. "
                "Сохраняется только результат проверки, без токенов.</p><p>Это отдельный тест, "
                "а не подключение Postiz.</p><a href=/authorize>Выбрать Google-аккаунт и канал</a>")
        if path.path == "/result":
            return self.page(self.server.last_message)
        if self.server.done:
            return self.page("Проверка уже завершена. Перезапустите инструмент для нового теста.", 409)
        if path.path == "/authorize":
            self.send_response(302)
            self.send_header("Location", self.server.authorization_url())
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path.path != "/oauth/callback":
            return self.page("Страница не найдена.", 404)
        query = urllib.parse.parse_qs(path.query)
        supplied_state = query.get("state", [""])[0]
        with self.server.lock:
            if not self.server.state or not secrets.compare_digest(supplied_state, self.server.state):
                return self.page("Проверка состояния не пройдена. Начните подключение заново.", 400)
            verifier = self.server.verifier
            self.server.state = self.server.verifier = None
        if query.get("error") or len(query.get("code", [])) != 1:
            return self.page("Google не выдал разрешение. Можно начать проверку заново с главной страницы.", 400)
        try:
            result = self.server.inspect_channel(query["code"][0], verifier)
        except (urllib.error.URLError, ValueError, KeyError) as error:
            if isinstance(error, urllib.error.HTTPError):
                detail = "HTTP " + str(error.code)
            elif isinstance(error, urllib.error.URLError):
                detail = type(error.reason).__name__
            else:
                detail = type(error).__name__
            self.server.last_message = "<h1>Проверка не завершена</h1><p>" + html.escape(detail) + \
                ". Секреты, коды и токены не сохранены.</p><a href=/>Начать заново</a>"
            return self.result_redirect()
        self.server.done = True
        listing = "".join("<li>" + html.escape(item["title"]) + " — " + html.escape(item.get("handle") or item["id"]) + "</li>" for item in result["channels"])
        revoke = "Тестовый доступ отозван." if result["test_access_revoked"] else "Отзыв тестового доступа не подтверждён — проверьте разрешения в Google-аккаунте."
        self.server.last_message = "<h1>Ответ YouTube API получен</h1><ul>" + listing + "</ul><p>" + revoke + \
                         " Публикация видео не проверялась. Postiz ещё не подключён.</p>"
        return self.result_redirect()

    def result_redirect(self):
        # Remove the single-use authorization code from the visible address bar.
        self.send_response(303)
        self.send_header("Location", "/result")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True, help="Private Google OAuth web-client JSON")
    parser.add_argument("--output", default="research/private/youtube-read-check.json")
    args = parser.parse_args()
    server = Probe(load_client(args.client), args.output)
    print("Open http://localhost:8789/ — read-only, local-only check.", flush=True)
    try:
        while time.monotonic() < server.deadline:
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
