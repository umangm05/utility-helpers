#!/usr/bin/env python3
"""Known-answer tests for all 10 Utility Helpers tools.

Each test loads the tool page in a fresh browser context, enters a known
input, and verifies the expected output. This satisfies the UH-BUILD-TOOLS
deliverable: "Evidence: test log showing each tool's known-answer test passing."

Usage:
    python3 scripts/test_tools.py [--port 8099]
"""

from __future__ import annotations

import argparse
import http.server
import json
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def free_port(preferred: int) -> int:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", preferred))
        s.close()
        return preferred
    except OSError:
        s.close()
        s2 = socket.socket()
        s2.bind(("127.0.0.1", 0))
        port = s2.getsockname()[1]
        s2.close()
        return port


def serve(root: Path, port: int):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)
        def log_message(self, format, *args):
            pass
    httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


# --------------------------------------------------------------------------- #
# Known-answer tests
# --------------------------------------------------------------------------- #

def test_word_counter(page, base: str) -> dict:
    """Test: 'Hello world' → 2 words, 11 chars, 10 no-space, 1 sentence, 1 paragraph."""
    page.goto(base + "/word-counter/", wait_until="domcontentloaded")
    page.fill("#wc-input", "Hello world")
    page.wait_for_timeout(200)
    words = page.text_content("#wc-words")
    chars = page.text_content("#wc-chars")
    chars_ns = page.text_content("#wc-chars-nospace")
    sentences = page.text_content("#wc-sentences")
    paragraphs = page.text_content("#wc-paragraphs")
    observed = {"words": int(words), "chars": int(chars), "chars_no_space": int(chars_ns), "sentences": int(sentences), "paragraphs": int(paragraphs)}
    expected = {"words": 2, "chars": 11, "chars_no_space": 10, "sentences": 1, "paragraphs": 1}
    return {"name": "word-counter", "input": "Hello world", "expected": expected, "observed": observed, "pass": observed == expected}


def test_password_generator(page, base: str) -> dict:
    """Test: generate 16-char password with all character types → matches regex."""
    page.goto(base + "/password-generator/", wait_until="domcontentloaded")
    page.fill("#pg-length", "16")
    page.check("#pg-upper")
    page.check("#pg-lower")
    page.check("#pg-numbers")
    page.check("#pg-symbols")
    page.click("#pg-generate")
    page.wait_for_timeout(200)
    pwd = page.input_value("#pg-output")
    observed = {"password": pwd, "length": len(pwd)}
    expected_pattern = r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{16}$"
    import re
    passed = bool(re.match(expected_pattern, pwd))
    return {"name": "password-generator", "input": "length=16, all char types", "expected": "matches " + expected_pattern, "observed": observed, "pass": passed}


def test_unit_converter(page, base: str) -> dict:
    """Test: 1 km → m = 1000."""
    page.goto(base + "/unit-converter/", wait_until="domcontentloaded")
    page.select_option("#uc-category", "length")
    page.wait_for_timeout(200)
    page.select_option("#uc-from", "km")
    page.select_option("#uc-to", "m")
    page.fill("#uc-input", "1")
    page.wait_for_timeout(200)
    result = page.text_content("#uc-result")
    observed = {"result": result.strip()}
    passed = "1000" in result
    return {"name": "unit-converter", "input": "1 km → m", "expected": "1000 m", "observed": observed, "pass": passed}


def test_json_formatter(page, base: str) -> dict:
    """Test: minified JSON → formatted with indentation."""
    page.goto(base + "/json-formatter/", wait_until="domcontentloaded")
    page.fill("#jf-input", '{"a":1,"b":2}')
    page.click("#jf-format")
    page.wait_for_timeout(200)
    output = page.input_value("#jf-output")
    error_visible = page.is_visible("#jf-error")
    observed = {"output": output, "error_visible": error_visible}
    expected = '{\n  "a": 1,\n  "b": 2\n}'
    passed = output == expected and not error_visible
    return {"name": "json-formatter", "input": '{"a":1,"b":2}', "expected": expected, "observed": observed, "pass": passed}


def test_base64(page, base: str) -> dict:
    """Test: 'Hello' → Base64 = 'SGVsbG8='."""
    page.goto(base + "/base64-encoder-decoder/", wait_until="domcontentloaded")
    page.fill("#b64-input", "Hello")
    page.click("#b64-encode")
    page.wait_for_timeout(200)
    output = page.input_value("#b64-output")
    observed = {"output": output}
    expected = "SGVsbG8="
    return {"name": "base64-encoder-decoder", "input": "Hello", "expected": expected, "observed": observed, "pass": output == expected}


def test_url_encoder(page, base: str) -> dict:
    """Test: 'hello world' → 'hello%20world'."""
    page.goto(base + "/url-encoder-decoder/", wait_until="domcontentloaded")
    page.fill("#url-input", "hello world")
    page.click("#url-encode")
    page.wait_for_timeout(200)
    output = page.input_value("#url-output")
    observed = {"output": output}
    expected = "hello%20world"
    return {"name": "url-encoder-decoder", "input": "hello world", "expected": expected, "observed": observed, "pass": output == expected}


def test_color_picker(page, base: str) -> dict:
    """Test: #ff0000 → rgb(255, 0, 0)."""
    page.goto(base + "/color-picker/", wait_until="domcontentloaded")
    page.fill("#cp-hex", "#ff0000")
    page.dispatch_event("#cp-hex", "change")
    page.wait_for_timeout(300)
    hex_val = page.input_value("#cp-hex")
    rgb_val = page.input_value("#cp-rgb")
    hsl_val = page.input_value("#cp-hsl")
    observed = {"hex": hex_val, "rgb": rgb_val, "hsl": hsl_val}
    passed = hex_val == "#ff0000" and "255" in rgb_val and "0" in rgb_val
    return {"name": "color-picker", "input": "#ff0000", "expected": "hex=#ff0000, rgb contains 255,0", "observed": observed, "pass": passed}


def test_timestamp_converter(page, base: str) -> dict:
    """Test: timestamp 0 → 1970-01-01."""
    page.goto(base + "/timestamp-converter/", wait_until="domcontentloaded")
    page.fill("#ts-input", "0")
    page.click("#ts-convert")
    page.wait_for_timeout(200)
    output = page.text_content("#ts-output")
    observed = {"output": output}
    passed = "1970" in output
    return {"name": "timestamp-converter", "input": "0", "expected": "contains 1970", "observed": observed, "pass": passed}


def test_text_case_converter(page, base: str) -> dict:
    """Test: 'hello world' → title case = 'Hello World'."""
    page.goto(base + "/text-case-converter/", wait_until="domcontentloaded")
    page.fill("#tc-input", "hello world")
    page.select_option("#tc-format", "title")
    page.wait_for_timeout(200)
    output = page.input_value("#tc-output")
    observed = {"output": output}
    expected = "Hello World"
    return {"name": "text-case-converter", "input": "hello world (title)", "expected": expected, "observed": observed, "pass": output == expected}


def test_lorem_ipsum(page, base: str) -> dict:
    """Test: generate 1 paragraph → non-empty text containing 'lorem'."""
    page.goto(base + "/lorem-ipsum-generator/", wait_until="domcontentloaded")
    page.fill("#li-count", "1")
    page.select_option("#li-type", "paragraphs")
    page.click("#li-generate")
    page.wait_for_timeout(200)
    output = page.input_value("#li-output")
    observed = {"output_preview": output[:100], "length": len(output)}
    passed = len(output) > 0 and "lorem" in output.lower()
    return {"name": "lorem-ipsum-generator", "input": "1 paragraph", "expected": "non-empty, contains 'lorem'", "observed": observed, "pass": passed}


# --------------------------------------------------------------------------- #
# Test runner
# --------------------------------------------------------------------------- #

ALL_TESTS = [
    test_word_counter,
    test_password_generator,
    test_unit_converter,
    test_json_formatter,
    test_base64,
    test_url_encoder,
    test_color_picker,
    test_timestamp_converter,
    test_text_case_converter,
    test_lorem_ipsum,
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8099)
    args = ap.parse_args()

    port = free_port(args.port)
    base = f"http://127.0.0.1:{port}"
    httpd = serve(ROOT, port)
    time.sleep(0.4)

    print(f"Running known-answer tests against {base}\n")
    print("=" * 70)

    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for test_fn in ALL_TESTS:
            ctx = browser.new_context()
            page = ctx.new_page()
            try:
                result = test_fn(page, base)
            except Exception as e:
                result = {"name": test_fn.__name__, "pass": False, "error": str(e)}
            results.append(result)
            status = "PASS" if result["pass"] else "FAIL"
            print(f"\n  [{status}] {result['name']}")
            print(f"    Input:    {result.get('input', 'N/A')}")
            print(f"    Expected: {result.get('expected', 'N/A')}")
            print(f"    Observed: {result.get('observed', 'N/A')}")
            if not result["pass"] and "error" in result:
                print(f"    Error:    {result['error']}")
            ctx.close()
        browser.close()

    httpd.shutdown()

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    print(f"\nResults: {passed}/{total} passed")

    if passed < total:
        print("\nFailed tests:")
        for r in results:
            if not r["pass"]:
                print(f"  - {r['name']}")
        return 1

    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
