#!/usr/bin/env python3
"""Generate tool pages for Utility Helpers from Edith's content JSON.

Reads the UH-RESEARCH output (utility-helpers-content.json) and produces
a site.config.json with all 10 tools, each with a self-contained body_html
(the tool's UI + inline JavaScript). Then runs the build.

Usage:
    python3 scripts/generate_tools.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "site.config.json"

# Edith's content JSON — path relative to the common KB
CONTENT_JSON = Path("/root/.hermes/common/team-discussion/edith/utility-helpers-content.json")


# --------------------------------------------------------------------------- #
# Tool body_html generators
# --------------------------------------------------------------------------- #

def word_counter_html() -> str:
    return '''\
<div class="tool">
  <label for="wc-input">Enter your text</label>
  <textarea id="wc-input" placeholder="Type or paste your text here..." rows="8"></textarea>
  <div id="wc-stats" style="margin-top:1rem;display:grid;gap:.5rem;grid-template-columns:repeat(auto-fit,minmax(10rem,1fr))">
    <div><span style="color:var(--muted)">Words</span><br><strong id="wc-words" style="font-size:1.5rem">0</strong></div>
    <div><span style="color:var(--muted)">Characters</span><br><strong id="wc-chars" style="font-size:1.5rem">0</strong></div>
    <div><span style="color:var(--muted)">No spaces</span><br><strong id="wc-chars-nospace" style="font-size:1.5rem">0</strong></div>
    <div><span style="color:var(--muted)">Sentences</span><br><strong id="wc-sentences" style="font-size:1.5rem">0</strong></div>
    <div><span style="color:var(--muted)">Paragraphs</span><br><strong id="wc-paragraphs" style="font-size:1.5rem">0</strong></div>
  </div>
</div>
<script>
(function() {
  var input = document.getElementById('wc-input');
  var words = document.getElementById('wc-words');
  var chars = document.getElementById('wc-chars');
  var charsNoSpace = document.getElementById('wc-chars-nospace');
  var sentences = document.getElementById('wc-sentences');
  var paragraphs = document.getElementById('wc-paragraphs');
  input.addEventListener('input', function() {
    var text = input.value;
    var wc = text.trim() ? text.trim().split(/\\s+/).length : 0;
    var cc = text.length;
    var ccns = text.replace(/\\s/g, '').length;
    var sc = text.split(/[.!?]+/).filter(function(s) { return s.trim(); }).length;
    var pc = text.split(/\\n\\n+/).filter(function(p) { return p.trim(); }).length;
    words.textContent = wc;
    chars.textContent = cc;
    charsNoSpace.textContent = ccns;
    sentences.textContent = sc;
    paragraphs.textContent = pc;
  });
})();
</script>'''


def password_generator_html() -> str:
    return '''\
<div class="tool">
  <div style="display:grid;gap:1rem;max-width:24rem">
    <div>
      <label for="pg-length">Password length</label>
      <input type="number" id="pg-length" value="16" min="4" max="128" style="width:100%">
    </div>
    <div style="display:grid;gap:.5rem">
      <label><input type="checkbox" id="pg-upper" checked> Uppercase (A-Z)</label>
      <label><input type="checkbox" id="pg-lower" checked> Lowercase (a-z)</label>
      <label><input type="checkbox" id="pg-numbers" checked> Numbers (0-9)</label>
      <label><input type="checkbox" id="pg-symbols" checked> Symbols (!@#$...)</label>
    </div>
    <button id="pg-generate" type="button">Generate password</button>
    <div>
      <label for="pg-output">Generated password</label>
      <input type="text" id="pg-output" readonly style="width:100%;font-family:monospace">
    </div>
    <button id="pg-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Copy to clipboard</button>
  </div>
</div>
<script>
(function() {
  var len = document.getElementById('pg-length');
  var upper = document.getElementById('pg-upper');
  var lower = document.getElementById('pg-lower');
  var numbers = document.getElementById('pg-numbers');
  var symbols = document.getElementById('pg-symbols');
  var output = document.getElementById('pg-output');
  var generate = document.getElementById('pg-generate');
  var copy = document.getElementById('pg-copy');
  function generatePassword() {
    var chars = '';
    if (upper.checked) chars += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    if (lower.checked) chars += 'abcdefghijklmnopqrstuvwxyz';
    if (numbers.checked) chars += '0123456789';
    if (symbols.checked) chars += '!@#$%^&*()_+-=[]{}|;:,.<>?';
    if (!chars) { output.value = ''; return; }
    var length = Math.max(4, Math.min(128, parseInt(len.value, 10) || 16));
    var arr = new Uint32Array(length);
    crypto.getRandomValues(arr);
    var pwd = '';
    for (var i = 0; i < length; i++) pwd += chars[arr[i] % chars.length];
    output.value = pwd;
  }
  generate.addEventListener('click', generatePassword);
  copy.addEventListener('click', function() { window.uhCopy(output.value); });
  generatePassword();
})();
</script>'''


def unit_converter_html() -> str:
    return '''\
<div class="tool">
  <div style="display:grid;gap:1rem;max-width:28rem">
    <div>
      <label for="uc-category">Category</label>
      <select id="uc-category" style="width:100%">
        <option value="length">Length</option>
        <option value="weight">Weight</option>
        <option value="temperature">Temperature</option>
        <option value="volume">Volume</option>
        <option value="area">Area</option>
        <option value="speed">Speed</option>
        <option value="time">Time</option>
        <option value="data">Data storage</option>
      </select>
    </div>
    <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:.5rem;align-items:end">
      <div>
        <label for="uc-from">From</label>
        <select id="uc-from" style="width:100%"></select>
      </div>
      <button id="uc-swap" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border);padding:.6rem .8rem">&harr;</button>
      <div>
        <label for="uc-to">To</label>
        <select id="uc-to" style="width:100%"></select>
      </div>
    </div>
    <div>
      <label for="uc-input">Value</label>
      <input type="number" id="uc-input" value="1" step="any" style="width:100%">
    </div>
    <div>
      <label>Result</label>
      <div id="uc-result" style="font-size:1.5rem;font-weight:700;padding:.75rem;border:1px solid var(--border);border-radius:8px;background:var(--panel-2)">—</div>
    </div>
  </div>
</div>
<script>
(function() {
  var UNITS = {
    length: { 'm': 1, 'km': 1000, 'cm': 0.01, 'mm': 0.001, 'mi': 1609.344, 'yd': 0.9144, 'ft': 0.3048, 'in': 0.0254 },
    weight: { 'kg': 1, 'g': 0.001, 'lb': 0.453592, 'oz': 0.0283495, 't': 1000 },
    temperature: { 'C': 'C', 'F': 'F', 'K': 'K' },
    volume: { 'L': 1, 'mL': 0.001, 'gal': 3.78541, 'qt': 0.946353, 'pt': 0.473176, 'cup': 0.236588, 'fl oz': 0.0295735 },
    area: { 'm2': 1, 'km2': 1e6, 'ft2': 0.092903, 'ac': 4046.86, 'ha': 10000 },
    speed: { 'm/s': 1, 'km/h': 0.277778, 'mph': 0.44704, 'ft/s': 0.3048, 'kn': 0.514444 },
    time: { 's': 1, 'min': 60, 'h': 3600, 'day': 86400, 'week': 604800, 'ms': 0.001 },
    data: { 'B': 1, 'KB': 1024, 'MB': 1048576, 'GB': 1073741824, 'TB': 1099511627776, 'bit': 0.125 }
  };
  var category = document.getElementById('uc-category');
  var from = document.getElementById('uc-from');
  var to = document.getElementById('uc-to');
  var input = document.getElementById('uc-input');
  var result = document.getElementById('uc-result');
  var swap = document.getElementById('uc-swap');
  function populateUnits() {
    var units = Object.keys(UNITS[category.value]);
    from.innerHTML = units.map(function(u) { return '<option value="' + u + '">' + u + '</option>'; }).join('');
    to.innerHTML = units.map(function(u) { return '<option value="' + u + '">' + u + '</option>'; }).join('');
    if (units.length > 1) to.selectedIndex = 1;
    convert();
  }
  function convert() {
    var val = parseFloat(input.value);
    if (isNaN(val)) { result.textContent = '—'; return; }
    var cat = category.value;
    var f = from.value, t = to.value;
    var out;
    if (cat === 'temperature') {
      var celsius = f === 'C' ? val : f === 'F' ? (val - 32) * 5/9 : val - 273.15;
      out = t === 'C' ? celsius : t === 'F' ? celsius * 9/5 + 32 : celsius + 273.15;
    } else {
      out = val * UNITS[cat][f] / UNITS[cat][t];
    }
    result.textContent = (Math.round(out * 1e10) / 1e10).toString() + ' ' + t;
  }
  category.addEventListener('change', populateUnits);
  from.addEventListener('change', convert);
  to.addEventListener('change', convert);
  input.addEventListener('input', convert);
  swap.addEventListener('click', function() {
    var tmp = from.value; from.value = to.value; to.value = tmp; convert();
  });
  populateUnits();
})();
</script>'''


def json_formatter_html() -> str:
    return '''\
<div class="tool">
  <div style="display:grid;gap:1rem">
    <div>
      <label for="jf-input">Paste your JSON</label>
      <textarea id="jf-input" placeholder=\'{"key":"value"}\' rows="8"></textarea>
    </div>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap">
      <button id="jf-format" type="button">Format</button>
      <button id="jf-minify" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Minify</button>
      <button id="jf-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Copy</button>
    </div>
    <div id="jf-error" style="color:#ef4444;display:none"></div>
    <div>
      <label for="jf-output">Result</label>
      <textarea id="jf-output" rows="8" readonly style="width:100%;font-family:monospace"></textarea>
    </div>
  </div>
</div>
<script>
(function() {
  var input = document.getElementById('jf-input');
  var output = document.getElementById('jf-output');
  var error = document.getElementById('jf-error');
  var format = document.getElementById('jf-format');
  var minify = document.getElementById('jf-minify');
  var copy = document.getElementById('jf-copy');
  function showError(msg) { error.textContent = msg; error.style.display = 'block'; output.value = ''; }
  function hideError() { error.style.display = 'none'; }
  function doFormat() {
    hideError();
    try {
      var parsed = JSON.parse(input.value);
      output.value = JSON.stringify(parsed, null, 2);
    } catch (e) { showError('Invalid JSON: ' + e.message); }
  }
  function doMinify() {
    hideError();
    try {
      var parsed = JSON.parse(input.value);
      output.value = JSON.stringify(parsed);
    } catch (e) { showError('Invalid JSON: ' + e.message); }
  }
  format.addEventListener('click', doFormat);
  minify.addEventListener('click', doMinify);
  copy.addEventListener('click', function() { window.uhCopy(output.value); });
})();
</script>'''


def base64_html() -> str:
    return '''\
<div class="tool">
  <div style="display:grid;gap:1rem">
    <div>
      <label for="b64-input">Enter text</label>
      <textarea id="b64-input" placeholder="Enter text to encode or decode..." rows="6"></textarea>
    </div>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap">
      <button id="b64-encode" type="button">Encode to Base64</button>
      <button id="b64-decode" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Decode from Base64</button>
      <button id="b64-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Copy</button>
    </div>
    <div id="b64-error" style="color:#ef4444;display:none"></div>
    <div>
      <label for="b64-output">Result</label>
      <textarea id="b64-output" rows="6" readonly style="width:100%;font-family:monospace"></textarea>
    </div>
  </div>
</div>
<script>
(function() {
  var input = document.getElementById('b64-input');
  var output = document.getElementById('b64-output');
  var error = document.getElementById('b64-error');
  var encode = document.getElementById('b64-encode');
  var decode = document.getElementById('b64-decode');
  var copy = document.getElementById('b64-copy');
  function showError(msg) { error.textContent = msg; error.style.display = 'block'; output.value = ''; }
  function hideError() { error.style.display = 'none'; }
  function doEncode() {
    hideError();
    try { output.value = btoa(unescape(encodeURIComponent(input.value))); }
    catch (e) { showError('Encoding error: ' + e.message); }
  }
  function doDecode() {
    hideError();
    try { output.value = decodeURIComponent(escape(atob(input.value.trim()))); }
    catch (e) { showError('Decoding error: ' + e.message); }
  }
  encode.addEventListener('click', doEncode);
  decode.addEventListener('click', doDecode);
  copy.addEventListener('click', function() { window.uhCopy(output.value); });
})();
</script>'''


def url_encoder_html() -> str:
    return '''\
<div class="tool">
  <div style="display:grid;gap:1rem">
    <div>
      <label for="url-input">Enter URL or text</label>
      <textarea id="url-input" placeholder="Enter URL or text to encode/decode..." rows="6"></textarea>
    </div>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap">
      <button id="url-encode" type="button">Encode</button>
      <button id="url-decode" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Decode</button>
      <button id="url-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Copy</button>
    </div>
    <div id="url-error" style="color:#ef4444;display:none"></div>
    <div>
      <label for="url-output">Result</label>
      <textarea id="url-output" rows="6" readonly style="width:100%;font-family:monospace"></textarea>
    </div>
  </div>
</div>
<script>
(function() {
  var input = document.getElementById('url-input');
  var output = document.getElementById('url-output');
  var error = document.getElementById('url-error');
  var encode = document.getElementById('url-encode');
  var decode = document.getElementById('url-decode');
  var copy = document.getElementById('url-copy');
  function showError(msg) { error.textContent = msg; error.style.display = 'block'; output.value = ''; }
  function hideError() { error.style.display = 'none'; }
  function doEncode() { hideError(); output.value = encodeURIComponent(input.value); }
  function doDecode() { hideError(); try { output.value = decodeURIComponent(input.value); } catch(e) { showError('Decoding error: ' + e.message); } }
  encode.addEventListener('click', doEncode);
  decode.addEventListener('click', doDecode);
  copy.addEventListener('click', function() { window.uhCopy(output.value); });
})();
</script>'''


def color_picker_html() -> str:
    return '''\
<div class="tool">
  <div style="display:grid;gap:1rem;max-width:28rem">
    <div>
      <label for="cp-picker">Pick a color</label>
      <input type="color" id="cp-picker" value="#f59e0b" style="width:100%;height:3rem;border:none;background:none;cursor:pointer">
    </div>
    <div id="cp-preview" style="height:4rem;border-radius:8px;border:1px solid var(--border);background:#f59e0b"></div>
    <div style="display:grid;gap:.5rem">
      <div>
        <label for="cp-hex">Hex</label>
        <input type="text" id="cp-hex" value="#f59e0b" style="width:100%;font-family:monospace">
      </div>
      <div>
        <label for="cp-rgb">RGB</label>
        <input type="text" id="cp-rgb" value="rgb(245, 158, 11)" style="width:100%;font-family:monospace">
      </div>
      <div>
        <label for="cp-hsl">HSL</label>
        <input type="text" id="cp-hsl" value="hsl(38, 92%, 50%)" style="width:100%;font-family:monospace">
      </div>
    </div>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap">
      <button id="cp-copy-hex" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Copy Hex</button>
      <button id="cp-copy-rgb" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Copy RGB</button>
      <button id="cp-copy-hsl" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Copy HSL</button>
    </div>
  </div>
</div>
<script>
(function() {
  var picker = document.getElementById('cp-picker');
  var preview = document.getElementById('cp-preview');
  var hex = document.getElementById('cp-hex');
  var rgb = document.getElementById('cp-rgb');
  var hsl = document.getElementById('cp-hsl');
  function hexToRgb(h) {
    h = h.replace('#', '');
    if (h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n = parseInt(h, 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }
  function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    var max = Math.max(r, g, b), min = Math.min(r, g, b);
    var h, s, l = (max + min) / 2;
    if (max === min) { h = s = 0; }
    else {
      var d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
      else if (max === g) h = ((b - r) / d + 2) / 6;
      else h = ((r - g) / d + 4) / 6;
    }
    return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
  }
  function update(hexVal) {
    var rgbObj = hexToRgb(hexVal);
    var hslObj = rgbToHsl(rgbObj.r, rgbObj.g, rgbObj.b);
    preview.style.background = hexVal;
    hex.value = hexVal;
    rgb.value = 'rgb(' + rgbObj.r + ', ' + rgbObj.g + ', ' + rgbObj.b + ')';
    hsl.value = 'hsl(' + hslObj.h + ', ' + hslObj.s + '%, ' + hslObj.l + '%)';
  }
  picker.addEventListener('input', function() { update(picker.value); });
  hex.addEventListener('change', function() {
    var v = hex.value.trim();
    if (!v.startsWith('#')) v = '#' + v;
    if (/^#[0-9a-fA-F]{3}$|^#[0-9a-fA-F]{6}$/.test(v)) { picker.value = v.length === 4 ? '#' + v[1]+v[1]+v[2]+v[2]+v[3]+v[3] : v; update(v); }
  });
  document.getElementById('cp-copy-hex').addEventListener('click', function() { window.uhCopy(hex.value); });
  document.getElementById('cp-copy-rgb').addEventListener('click', function() { window.uhCopy(rgb.value); });
  document.getElementById('cp-copy-hsl').addEventListener('click', function() { window.uhCopy(hsl.value); });
  update(picker.value);
})();
</script>'''


def timestamp_converter_html() -> str:
    return '''\
<div class="tool">
  <div style="display:grid;gap:1rem;max-width:28rem">
    <div>
      <label for="ts-input">Unix timestamp (seconds or milliseconds)</label>
      <input type="number" id="ts-input" placeholder="e.g. 1697452800" style="width:100%;font-family:monospace">
    </div>
    <button id="ts-convert" type="button">Convert to date</button>
    <div>
      <label>Human-readable date</label>
      <div id="ts-output" style="padding:.75rem;border:1px solid var(--border);border-radius:8px;background:var(--panel-2);font-family:monospace">—</div>
    </div>
    <hr style="border:none;border-top:1px solid var(--border);margin:1rem 0">
    <div>
      <label for="ts-date-input">Date to convert</label>
      <input type="datetime-local" id="ts-date-input" style="width:100%">
    </div>
    <button id="ts-to-timestamp" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Convert to timestamp</button>
    <div>
      <label>Unix timestamp</label>
      <div id="ts-timestamp-output" style="padding:.75rem;border:1px solid var(--border);border-radius:8px;background:var(--panel-2);font-family:monospace">—</div>
    </div>
  </div>
</div>
<script>
(function() {
  var tsInput = document.getElementById('ts-input');
  var tsOutput = document.getElementById('ts-output');
  var convert = document.getElementById('ts-convert');
  var dateInput = document.getElementById('ts-date-input');
  var tsTimestampOutput = document.getElementById('ts-timestamp-output');
  var toTimestamp = document.getElementById('ts-to-timestamp');
  function convertTs() {
    var val = parseFloat(tsInput.value);
    if (isNaN(val)) { tsOutput.textContent = '—'; return; }
    var ms = val < 1e12 ? val * 1000 : val;
    var d = new Date(ms);
    if (isNaN(d.getTime())) { tsOutput.textContent = 'Invalid timestamp'; return; }
    tsOutput.textContent = d.toLocaleString() + ' (' + d.toISOString() + ')';
  }
  function convertDate() {
    var val = dateInput.value;
    if (!val) { tsTimestampOutput.textContent = '—'; return; }
    var d = new Date(val);
    if (isNaN(d.getTime())) { tsTimestampOutput.textContent = 'Invalid date'; return; }
    var sec = Math.floor(d.getTime() / 1000);
    tsTimestampOutput.textContent = sec + ' (seconds) / ' + d.getTime() + ' (milliseconds)';
  }
  convert.addEventListener('click', convertTs);
  toTimestamp.addEventListener('click', convertDate);
  tsInput.addEventListener('input', convertTs);
})();
</script>'''


def text_case_converter_html() -> str:
    return '''\
<div class="tool">
  <div style="display:grid;gap:1rem">
    <div>
      <label for="tc-input">Enter your text</label>
      <textarea id="tc-input" placeholder="Type or paste your text here..." rows="6"></textarea>
    </div>
    <div>
      <label for="tc-format">Convert to</label>
      <select id="tc-format" style="width:100%">
        <option value="uppercase">UPPERCASE</option>
        <option value="lowercase">lowercase</option>
        <option value="sentence">Sentence case</option>
        <option value="title">Title Case</option>
        <option value="camel">camelCase</option>
        <option value="pascal">PascalCase</option>
        <option value="snake">snake_case</option>
      </select>
    </div>
    <button id="tc-convert" type="button">Convert</button>
    <div>
      <label for="tc-output">Result</label>
      <textarea id="tc-output" rows="6" readonly style="width:100%"></textarea>
    </div>
    <button id="tc-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Copy to clipboard</button>
  </div>
</div>
<script>
(function() {
  var input = document.getElementById('tc-input');
  var format = document.getElementById('tc-format');
  var output = document.getElementById('tc-output');
  var convert = document.getElementById('tc-convert');
  var copy = document.getElementById('tc-copy');
  function toWords(text) { return text.trim().split(/\\s+/).filter(Boolean); }
  function convertText() {
    var text = input.value;
    var fmt = format.value;
    var result = '';
    if (fmt === 'uppercase') result = text.toUpperCase();
    else if (fmt === 'lowercase') result = text.toLowerCase();
    else if (fmt === 'sentence') result = text.toLowerCase().replace(/(^\\s*[a-z])|[.!?]\\s+[a-z]/g, function(c) { return c.toUpperCase(); });
    else if (fmt === 'title') result = toWords(text).map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); }).join(' ');
    else if (fmt === 'camel') result = toWords(text).map(function(w, i) { return i === 0 ? w.toLowerCase() : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); }).join('');
    else if (fmt === 'pascal') result = toWords(text).map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); }).join('');
    else if (fmt === 'snake') result = toWords(text).map(function(w) { return w.toLowerCase(); }).join('_');
    output.value = result;
  }
  convert.addEventListener('click', convertText);
  copy.addEventListener('click', function() { window.uhCopy(output.value); });
  input.addEventListener('input', convertText);
  format.addEventListener('change', convertText);
})();
</script>'''


def lorem_ipsum_html() -> str:
    return '''\
<div class="tool">
  <div style="display:grid;gap:1rem;max-width:28rem">
    <div>
      <label for="li-count">How many?</label>
      <input type="number" id="li-count" value="3" min="1" max="20" style="width:100%">
    </div>
    <div>
      <label for="li-type">Type</label>
      <select id="li-type" style="width:100%">
        <option value="paragraphs">Paragraphs</option>
        <option value="sentences">Sentences</option>
        <option value="words">Words</option>
      </select>
    </div>
    <button id="li-generate" type="button">Generate</button>
    <div>
      <label for="li-output">Generated text</label>
      <textarea id="li-output" rows="10" readonly style="width:100%"></textarea>
    </div>
    <button id="li-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border)">Copy to clipboard</button>
  </div>
</div>
<script>
(function() {
  var LOREM = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.';
  var WORDS = LOREM.split(/\\s+/);
  var count = document.getElementById('li-count');
  var type = document.getElementById('li-type');
  var output = document.getElementById('li-output');
  var generate = document.getElementById('li-generate');
  var copy = document.getElementById('li-copy');
  function generateText() {
    var n = Math.max(1, Math.min(20, parseInt(count.value, 10) || 3));
    var t = type.value;
    var result = '';
    if (t === 'words') {
      result = WORDS.slice(0, n).join(' ');
    } else if (t === 'sentences') {
      var sentences = LOREM.match(/[^.!?]+[.!?]+/g) || [LOREM];
      result = [];
      for (var i = 0; i < n; i++) result.push(sentences[i % sentences.length]);
      result = result.join(' ');
    } else {
      var paragraphs = [];
      for (var i = 0; i < n; i++) {
        var start = (i * 5) % WORDS.length;
        var words = [];
        for (var j = 0; j < 5; j++) words.push(WORDS[(start + j) % WORDS.length]);
        paragraphs.push(words.join(' '));
      }
      result = paragraphs.join('\\n\\n');
    }
    output.value = result;
  }
  generate.addEventListener('click', generateText);
  copy.addEventListener('click', function() { window.uhCopy(output.value); });
  generateText();
})();
</script>'''


# --------------------------------------------------------------------------- #
# Tool registry
# --------------------------------------------------------------------------- #

TOOL_GENERATORS = {
    "word-counter": word_counter_html,
    "password-generator": password_generator_html,
    "unit-converter": unit_converter_html,
    "json-formatter": json_formatter_html,
    "base64-encoder-decoder": base64_html,
    "url-encoder-decoder": url_encoder_html,
    "color-picker": color_picker_html,
    "timestamp-converter": timestamp_converter_html,
    "text-case-converter": text_case_converter_html,
    "lorem-ipsum-generator": lorem_ipsum_html,
}


def main() -> int:
    if not CONTENT_JSON.exists():
        print(f"ERROR: content JSON not found at {CONTENT_JSON}")
        return 1

    content = json.loads(CONTENT_JSON.read_text(encoding="utf-8"))
    tools_data = content.get("tools", [])

    if len(tools_data) != 10:
        print(f"WARNING: expected 10 tools, found {len(tools_data)}")

    tools = []
    for tool_data in tools_data:
        slug = tool_data["slug"]
        generator = TOOL_GENERATORS.get(slug)
        if not generator:
            print(f"WARNING: no generator for tool '{slug}', skipping")
            continue

        body_html = generator()
        tools.append({
            "slug": slug,
            "name": tool_data["name"],
            "summary": tool_data["daily_usage_why"],
            "title": tool_data["seo"]["title"],
            "description": tool_data["seo"]["description"],
            "intro": tool_data["intro"],
            "faq": tool_data["faq"],
            "body_html": body_html,
        })

    # Read existing config and update tools
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["tools"] = tools
    CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {CONFIG.relative_to(ROOT)} with {len(tools)} tools")

    # Run the build
    print("\nRunning build...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build.py")],
        cwd=str(ROOT),
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
