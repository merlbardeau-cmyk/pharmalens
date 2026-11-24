"""Phase 0 classifier tests: guard against false greens and false reds."""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qa.phase0_probe import classify  # noqa: E402


def resp(status, body="", ct="text/html", url="https://x.test/"):
    return httpx.Response(status, content=body.encode(), headers={"content-type": ct}, request=httpx.Request("GET", url))


API = dict(expected="api")
DL = dict(expected="download")
HTML = dict(expected="html")


def test_waf_block_is_red():
    assert classify(HTML, resp(500, "Web Page Blocked! Attack ID: 20000051"), None, "no_robots")[0] == "red"


def test_oauth_code_challenge_is_not_captcha():
    body = "<a href='/login?code_challenge=abc'>login</a>" + "x" * 40_000
    assert classify(HTML, resp(200, body), None, "allowed")[0] == "yellow"


def test_real_challenge_page_is_red():
    assert classify(HTML, resp(403, "<title>Just a moment...</title> cf-challenge"), None, "no_robots")[0] == "red"


def test_robots_disallow_is_red_even_if_200():
    assert classify(API, resp(200, "{}", "application/json"), None, "disallowed")[0] == "red"


def test_api_needing_key_is_green():
    light, access, _ = classify(API, resp(403, "<fault>invalid key</fault>", "application/xml"), None, "no_robots")
    assert (light, access) == ("green", "api")


def test_fda_media_download_link_detected():
    body = '<a href="/media/192069/download?attachment">3rd Quarter 2026</a>' + "x" * 5000
    assert classify(DL, resp(200, body), None, "allowed")[0] == "green"


def test_download_page_without_links_is_yellow():
    assert classify(DL, resp(200, "<html>" + "x" * 5000 + "</html>"), None, "allowed")[0] == "yellow"


def test_unreachable_is_red():
    assert classify(HTML, None, "ConnectError", "unreachable")[0] == "red"
