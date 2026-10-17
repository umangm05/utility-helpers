#!/usr/bin/env python3
"""Known-answer functional tests for each tool page.

Exercises the interactive behavior of each tool via Playwright — types input,
clicks buttons, verifies expected output. This is NOT a static HTML check.
"""

import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "site.config.json").read_text())
TOOLS = CONFIG["tools"]

def run_tests():
    passed = 0
    failed = 0
    results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        for tool in TOOLS:
            slug = tool["slug"]
            name = tool["name"]
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:8102/{slug}/", wait_until="domcontentloaded")

            try:
                if slug == "word-counter":
                    page.fill("#wc-input", "Hello world! This is a test. How many words are here?")
                    page.wait_for_timeout(200)
                    words = page.text_content("#wc-words")
                    assert words == "11", f"Expected 11 words, got {words}"
                    chars = page.text_content("#wc-chars")
                    assert chars == "53", f"Expected 53 chars, got {chars}"
                    results.append(f"PASS  {slug}: 11 words, 53 chars")

                elif slug == "password-generator":
                    page.click("#pg-generate")
                    page.wait_for_timeout(200)
                    pwd = page.text_content("#pg-output")
                    assert len(pwd) == 16, f"Expected 16-char password, got {len(pwd)}"
                    # Change length
                    page.eval_on_selector("#pg-length", "el => { el.value = 24; el.dispatchEvent(new Event('input')); }")
                    page.click("#pg-generate")
                    page.wait_for_timeout(200)
                    pwd2 = page.text_content("#pg-output")
                    assert len(pwd2) == 24, f"Expected 24-char password, got {len(pwd2)}"
                    results.append(f"PASS  {slug}: 16→24 char passwords generated")

                elif slug == "unit-converter":
                    # 1 km = 1000 m
                    page.select_option("#uc-category", "length")
                    page.wait_for_timeout(100)
                    page.fill("#uc-input", "1")
                    page.select_option("#uc-from", "km")
                    page.select_option("#uc-to", "m")
                    page.wait_for_timeout(200)
                    result = page.text_content("#uc-result")
                    assert result == "1000", f"Expected 1000, got {result}"
                    # 0°C = 32°F
                    page.select_option("#uc-category", "temperature")
                    page.wait_for_timeout(100)
                    page.fill("#uc-input", "0")
                    page.select_option("#uc-from", "C")
                    page.select_option("#uc-to", "F")
                    page.wait_for_timeout(200)
                    result2 = page.text_content("#uc-result")
                    assert result2 == "32", f"Expected 32, got {result2}"
                    results.append(f"PASS  {slug}: 1km=1000m, 0°C=32°F")

                elif slug == "json-formatter":
                    page.fill("#jf-input", '{"name":"test","value":42,"active":true}')
                    page.click("#jf-format")
                    page.wait_for_timeout(200)
                    output = page.text_content("#jf-output")
                    assert '"name": "test"' in output, f"Formatted output missing key-value: {output[:100]}"
                    assert '"value": 42' in output, "Missing number"
                    # Test error
                    page.fill("#jf-input", "{invalid json}")
                    page.click("#jf-format")
                    page.wait_for_timeout(200)
                    err = page.text_content("#jf-error")
                    assert "Invalid JSON" in err, f"Expected error message, got: {err}"
                    results.append(f"PASS  {slug}: formatted + error detection")

                elif slug == "base64-encoder-decoder":
                    page.fill("#b64-input", "Hello, World!")
                    page.click("#b64-encode")
                    page.wait_for_timeout(200)
                    encoded = page.text_content("#b64-output")
                    assert encoded == "SGVsbG8sIFdvcmxkIQ==", f"Expected SGVsbG8sIFdvcmxkIQ==, got {encoded}"
                    # Decode back
                    page.fill("#b64-input", encoded)
                    page.click("#b64-decode")
                    page.wait_for_timeout(200)
                    decoded = page.text_content("#b64-output")
                    assert decoded == "Hello, World!", f"Expected Hello, World!, got {decoded}"
                    results.append(f"PASS  {slug}: encode+decode roundtrip")

                elif slug == "url-encoder-decoder":
                    page.fill("#url-input", "hello world & foo=bar")
                    page.click("#url-encode")
                    page.wait_for_timeout(200)
                    encoded = page.text_content("#url-output")
                    assert encoded == "hello%20world%20%26%20foo%3Dbar", f"Unexpected: {encoded}"
                    page.fill("#url-input", encoded)
                    page.click("#url-decode")
                    page.wait_for_timeout(200)
                    decoded = page.text_content("#url-output")
                    assert decoded == "hello world & foo=bar", f"Unexpected: {decoded}"
                    results.append(f"PASS  {slug}: encode+decode roundtrip")

                elif slug == "color-picker":
                    # Default color is #f59e0b -> rgb(245, 158, 11)
                    hex_val = page.eval_on_selector("#cp-hex", "el => el.value")
                    assert hex_val == "#f59e0b", f"Expected #f59e0b, got {hex_val}"
                    r = page.eval_on_selector("#cp-r", "el => el.value")
                    assert r == "245", f"Expected R=245, got {r}"
                    g = page.eval_on_selector("#cp-g", "el => el.value")
                    assert g == "158", f"Expected G=158, got {g}"
                    b = page.eval_on_selector("#cp-b", "el => el.value")
                    assert b == "11", f"Expected B=11, got {b}"
                    # Change hex
                    page.eval_on_selector("#cp-hex", "el => { el.value = '#ff0000'; el.dispatchEvent(new Event('change')); }")
                    page.wait_for_timeout(200)
                    r2 = page.eval_on_selector("#cp-r", "el => el.value")
                    assert r2 == "255", f"Expected R=255, got {r2}"
                    results.append(f"PASS  {slug}: hex↔rgb conversion verified")

                elif slug == "timestamp-converter":
                    # Set to known timestamp: 2026-01-01 00:00:00 UTC = 1767225600
                    page.fill("#ts-input", "1767225600")
                    page.wait_for_timeout(200)
                    utc = page.text_content("#ts-utc")
                    assert "2026" in utc, f"Expected 2026 in UTC, got {utc}"
                    seconds = page.text_content("#ts-seconds")
                    assert seconds == "1767225600", f"Expected 1767225600, got {seconds}"
                    ms = page.text_content("#ts-ms")
                    assert ms == "1767225600000", f"Expected 1767225600000, got {ms}"
                    results.append(f"PASS  {slug}: timestamp→date conversion verified")

                elif slug == "text-case-converter":
                    page.fill("#tc-input", "hello world")
                    page.click("button[data-type='upper']")
                    page.wait_for_timeout(100)
                    assert page.text_content("#tc-output") == "HELLO WORLD"
                    page.click("button[data-type='lower']")
                    page.wait_for_timeout(100)
                    assert page.text_content("#tc-output") == "hello world"
                    page.click("button[data-type='title']")
                    page.wait_for_timeout(100)
                    assert page.text_content("#tc-output") == "Hello World"
                    results.append(f"PASS  {slug}: upper/lower/title case")

                elif slug == "lorem-ipsum-generator":
                    page.select_option("#li-unit", "sentences")
                    page.eval_on_selector("#li-count", "el => { el.value = 5; }")
                    page.click("#li-generate")
                    page.wait_for_timeout(200)
                    output = page.text_content("#li-output")
                    sentences = [s.strip() for s in output.split('.') if s.strip()]
                    assert len(sentences) == 5, f"Expected 5 sentences, got {len(sentences)}"
                    results.append(f"PASS  {slug}: 5 sentences generated")

                passed += 1
            except AssertionError as e:
                results.append(f"FAIL  {slug}: {e}")
                failed += 1
            except Exception as e:
                results.append(f"ERROR {slug}: {e}")
                failed += 1
            finally:
                ctx.close()

        browser.close()

    return passed, failed, results


if __name__ == "__main__":
    # Start a local HTTP server
    import http.server
    import socketserver
    import threading
    import time

    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("127.0.0.1", 8102), handler)
    httpd.allow_reuse_address = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.5)

    passed, failed, results = run_tests()
    httpd.shutdown()

    print("\n=== KNOWN-ANSWER FUNCTIONAL TESTS ===")
    for r in results:
        print(f"  {r}")
    print(f"\n{passed}/{len(results)} tools passed")
    sys.exit(0 if failed == 0 else 1)
