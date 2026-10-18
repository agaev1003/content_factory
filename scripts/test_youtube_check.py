import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location("probe", Path(__file__).with_name("check_youtube_connection.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class YouTubeCheckTests(unittest.TestCase):
    def test_forged_state_never_exchanges_code(self):
        handler = Mock()
        handler.headers = {"Host": "localhost:8789"}
        handler.path = "/oauth/callback?state=forged&code=never-send"
        handler.server.state = "real-state"
        handler.server.done = False
        handler.server.lock = probe.threading.Lock()
        probe.Handler.do_GET(handler)
        handler.server.inspect_channel.assert_not_called()
        self.assertEqual(handler.page.call_args.args[1], 400)

    def test_pkce_and_only_readonly_scope(self):
        server = object.__new__(probe.Probe)
        server.client = {"client_id": "test-id"}
        query = probe.urllib.parse.parse_qs(probe.urllib.parse.urlsplit(server.authorization_url()).query)
        self.assertEqual(query["scope"], [probe.SCOPE])
        self.assertEqual(query["redirect_uri"], [probe.REDIRECT])
        self.assertEqual(query["access_type"], ["online"])
        self.assertEqual(query["state"], [server.state])
        expected = probe.base64.urlsafe_b64encode(probe.hashlib.sha256(server.verifier.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(query["code_challenge"], [expected])

    def test_client_requires_loopback_callback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "client.json"
            path.write_text(json.dumps({"web": {"client_id": "id", "client_secret": "secret", "redirect_uris": ["https://example.com"]}}))
            with self.assertRaises(ValueError):
                probe.load_client(path)

    def test_revoke_even_when_channel_request_fails(self):
        server = object.__new__(probe.Probe)
        server.client = {"client_id": "id", "client_secret": "secret"}
        with patch.object(probe, "post_form", side_effect=[{"access_token": "never-save", "scope": probe.SCOPE}, {}]) as form:
            with patch.object(probe.urllib.request, "urlopen", side_effect=probe.urllib.error.URLError("offline")):
                with self.assertRaises(probe.urllib.error.URLError):
                    server.inspect_channel("test-code", "test-verifier")
            self.assertEqual(form.call_args.args, (probe.REVOKE, {"token": "never-save"}))

    def test_report_does_not_store_credentials_or_tokens(self):
        from io import BytesIO
        with tempfile.TemporaryDirectory() as folder:
            server = object.__new__(probe.Probe)
            server.client = {"client_id": "id", "client_secret": "private-secret"}
            server.output = Path(folder) / "result.json"
            response = BytesIO(json.dumps({"items": [{"id": "channel-id", "snippet": {"title": "Test", "customUrl": "@test"}}]}).encode())
            with patch.object(probe, "post_form", side_effect=[{"access_token": "private-token", "scope": probe.SCOPE}, {}]):
                with patch.object(probe.urllib.request, "urlopen", return_value=response):
                    result = server.inspect_channel("private-code", "private-verifier")
            saved = server.output.read_text()
            self.assertNotIn("private-", saved)
            self.assertTrue(result["test_access_revoked"])
            self.assertFalse(result["upload_tested"])
            self.assertEqual(server.output.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
