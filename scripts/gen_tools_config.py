#!/usr/bin/env python3
"""Generate site.config.json with all 10 tool definitions from Edith's research.

Reads common/team-discussion/edith/utility-helpers-content.json and produces
a complete site.config.json with body_html for each tool's interactive UI.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = Path("/home/com194/.hermes/common/team-discussion/edith/utility-helpers-content.json")

# Summary overrides — one-line descriptions for the home page tiles
SUMMARIES = {
    "word-counter": "Count words, characters, sentences and paragraphs in your text instantly.",
    "password-generator": "Create strong, random passwords with custom length and character types.",
    "unit-converter": "Convert between length, weight, temperature, volume, area, speed and more.",
    "json-formatter": "Format, validate, and beautify JSON data with syntax highlighting.",
    "base64-encoder-decoder": "Encode and decode Base64 text instantly — no server, no upload.",
    "url-encoder-decoder": "Encode and decode URLs with percent-encoding, right in your browser.",
    "color-picker": "Pick colors and convert between Hex, RGB, and HSL with live preview.",
    "timestamp-converter": "Convert Unix timestamps to readable dates and back, with UTC support.",
    "text-case-converter": "Transform text between uppercase, lowercase, title case, camelCase and more.",
    "lorem-ipsum-generator": "Generate lorem ipsum placeholder text by paragraph, sentence, or word.",
}

# Inline JavaScript for each tool — loaded per-page via <script> in body_html
TOOL_SCRIPTS = {}

TOOL_SCRIPTS["word-counter"] = r"""
<script>
(function() {
  var input = document.getElementById('wc-input');
  var wordsEl = document.getElementById('wc-words');
  var charsEl = document.getElementById('wc-chars');
  var charsNoSpaceEl = document.getElementById('wc-chars-ns');
  var sentencesEl = document.getElementById('wc-sentences');
  var paragraphsEl = document.getElementById('wc-paragraphs');

  function countWords(text) {
    var trimmed = text.trim();
    if (!trimmed) return 0;
    return trimmed.split(/\s+/).length;
  }
  function countSentences(text) {
    var trimmed = text.trim();
    if (!trimmed) return 0;
    var matches = trimmed.match(/[.!?]+(\s|$)/g);
    return matches ? matches.length : (trimmed.length > 0 ? 1 : 0);
  }
  function countParagraphs(text) {
    var trimmed = text.trim();
    if (!trimmed) return 0;
    return trimmed.split(/\n\s*\n+/).filter(function(p) { return p.trim().length > 0; }).length;
  }
  function update() {
    var text = input.value;
    wordsEl.textContent = countWords(text);
    charsEl.textContent = text.length;
    charsNoSpaceEl.textContent = text.replace(/\s/g, '').length;
    sentencesEl.textContent = countSentences(text);
    paragraphsEl.textContent = countParagraphs(text);
  }
  input.addEventListener('input', update);
  update();
})();
</script>
"""

TOOL_SCRIPTS["password-generator"] = r"""
<script>
(function() {
  var lengthEl = document.getElementById('pg-length');
  var lengthVal = document.getElementById('pg-length-val');
  var upperEl = document.getElementById('pg-upper');
  var lowerEl = document.getElementById('pg-lower');
  var numbersEl = document.getElementById('pg-numbers');
  var symbolsEl = document.getElementById('pg-symbols');
  var outputEl = document.getElementById('pg-output');
  var generateBtn = document.getElementById('pg-generate');
  var copyBtn = document.getElementById('pg-copy');

  function generate() {
    var length = parseInt(lengthEl.value, 10);
    var chars = '';
    if (upperEl.checked) chars += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    if (lowerEl.checked) chars += 'abcdefghijklmnopqrstuvwxyz';
    if (numbersEl.checked) chars += '0123456789';
    if (symbolsEl.checked) chars += '!@#$%^&*()_+-=[]{}|;:,.<>?';

    if (!chars) {
      outputEl.textContent = 'Select at least one character type';
      return;
    }
    var arr = new Uint32Array(length);
    crypto.getRandomValues(arr);
    var password = '';
    for (var i = 0; i < length; i++) {
      password += chars[arr[i] % chars.length];
    }
    outputEl.textContent = password;
  }

  lengthEl.addEventListener('input', function() {
    lengthVal.textContent = lengthEl.value;
  });
  generateBtn.addEventListener('click', generate);
  copyBtn.addEventListener('click', function() {
    window.uhCopy(outputEl.textContent);
  });
  generate();
})();
</script>
"""

TOOL_SCRIPTS["unit-converter"] = r"""
<script>
(function() {
  var categoryEl = document.getElementById('uc-category');
  var fromEl = document.getElementById('uc-from');
  var toEl = document.getElementById('uc-to');
  var inputEl = document.getElementById('uc-input');
  var resultEl = document.getElementById('uc-result');

  var UNITS = {
    length: { base: 'm', units: { m: 1, km: 1000, cm: 0.01, mm: 0.001, mi: 1609.344, yd: 0.9144, ft: 0.3048, in: 0.0254 } },
    weight: { base: 'kg', units: { kg: 1, g: 0.001, mg: 0.000001, lb: 0.453592, oz: 0.0283495, st: 6.35029 } },
    temperature: { special: true },
    volume: { base: 'l', units: { l: 1, ml: 0.001, m3: 1000, gal: 3.78541, qt: 0.946353, pt: 0.473176, cup: 0.236588, floz: 0.0295735 } },
    area: { base: 'm2', units: { m2: 1, km2: 1000000, cm2: 0.0001, ha: 10000, ac: 4046.86, ft2: 0.092903, in2: 0.00064516 } },
    speed: { base: 'mps', units: { mps: 1, kph: 0.277778, mph: 0.44704, knot: 0.514444 } },
    time: { base: 's', units: { s: 1, min: 60, h: 3600, day: 86400, week: 604800, month: 2629746, year: 31556952 } },
    data: { base: 'b', units: { b: 1, kb: 1024, mb: 1048576, gb: 1073741824, tb: 1099511627776 } }
  };

  function populateUnits() {
    var cat = categoryEl.value;
    var config = UNITS[cat];
    var unitNames = config.special ? ['C', 'F', 'K'] : Object.keys(config.units);
    fromEl.innerHTML = '';
    toEl.innerHTML = '';
    unitNames.forEach(function(u) {
      fromEl.appendChild(new Option(u, u));
      toEl.appendChild(new Option(u, u));
    });
    if (unitNames.length > 1) toEl.selectedIndex = 1;
    convert();
  }

  function convertTemperature(value, from, to) {
    var celsius;
    if (from === 'C') celsius = value;
    else if (from === 'F') celsius = (value - 32) * 5 / 9;
    else celsius = value - 273.15;

    if (to === 'C') return celsius;
    if (to === 'F') return celsius * 9 / 5 + 32;
    return celsius + 273.15;
  }

  function convert() {
    var cat = categoryEl.value;
    var config = UNITS[cat];
    var value = parseFloat(inputEl.value);
    if (isNaN(value)) { resultEl.textContent = '—'; return; }
    var from = fromEl.value, to = toEl.value;
    var result;
    if (config.special) {
      result = convertTemperature(value, from, to);
    } else {
      var baseValue = value * config.units[from];
      result = baseValue / config.units[to];
    }
    resultEl.textContent = (Math.abs(result) < 0.000001 || Math.abs(result) > 1e9)
      ? result.toExponential(6)
      : parseFloat(result.toFixed(10)).toString();
  }

  categoryEl.addEventListener('change', populateUnits);
  fromEl.addEventListener('change', convert);
  toEl.addEventListener('change', convert);
  inputEl.addEventListener('input', convert);
  populateUnits();
})();
</script>
"""

TOOL_SCRIPTS["json-formatter"] = r"""
<script>
(function() {
  var inputEl = document.getElementById('jf-input');
  var outputEl = document.getElementById('jf-output');
  var formatBtn = document.getElementById('jf-format');
  var minifyBtn = document.getElementById('jf-minify');
  var errorEl = document.getElementById('jf-error');
  var copyBtn = document.getElementById('jf-copy');

  function highlight(json) {
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function(match) {
      var cls = 'json-number';
      if (/^"/.test(match)) {
        cls = /:$/.test(match) ? 'json-key' : 'json-string';
      } else if (/true|false/.test(match)) {
        cls = 'json-boolean';
      } else if (/null/.test(match)) {
        cls = 'json-null';
      }
      return '<span class="' + cls + '">' + match + '</span>';
    });
  }

  function formatJSON() {
    errorEl.textContent = '';
    try {
      var parsed = JSON.parse(inputEl.value);
      var formatted = JSON.stringify(parsed, null, 2);
      outputEl.innerHTML = highlight(formatted);
    } catch(e) {
      outputEl.textContent = '';
      errorEl.textContent = 'Invalid JSON: ' + e.message;
    }
  }

  function minifyJSON() {
    errorEl.textContent = '';
    try {
      var parsed = JSON.parse(inputEl.value);
      outputEl.textContent = JSON.stringify(parsed);
    } catch(e) {
      outputEl.textContent = '';
      errorEl.textContent = 'Invalid JSON: ' + e.message;
    }
  }

  formatBtn.addEventListener('click', formatJSON);
  minifyBtn.addEventListener('click', minifyJSON);
  copyBtn.addEventListener('click', function() {
    window.uhCopy(outputEl.textContent);
  });
})();
</script>
"""

TOOL_SCRIPTS["base64-encoder-decoder"] = r"""
<script>
(function() {
  var inputEl = document.getElementById('b64-input');
  var outputEl = document.getElementById('b64-output');
  var encodeBtn = document.getElementById('b64-encode');
  var decodeBtn = document.getElementById('b64-decode');
  var copyBtn = document.getElementById('b64-copy');
  var errorEl = document.getElementById('b64-error');

  function encode() {
    errorEl.textContent = '';
    try {
      outputEl.textContent = btoa(unescape(encodeURIComponent(inputEl.value)));
    } catch(e) {
      errorEl.textContent = 'Error: ' + e.message;
    }
  }

  function decode() {
    errorEl.textContent = '';
    try {
      outputEl.textContent = decodeURIComponent(escape(atob(inputEl.value)));
    } catch(e) {
      errorEl.textContent = 'Error: Invalid Base64 input';
    }
  }

  encodeBtn.addEventListener('click', encode);
  decodeBtn.addEventListener('click', decode);
  copyBtn.addEventListener('click', function() {
    window.uhCopy(outputEl.textContent);
  });
})();
</script>
"""

TOOL_SCRIPTS["url-encoder-decoder"] = r"""
<script>
(function() {
  var inputEl = document.getElementById('url-input');
  var outputEl = document.getElementById('url-output');
  var encodeBtn = document.getElementById('url-encode');
  var decodeBtn = document.getElementById('url-decode');
  var copyBtn = document.getElementById('url-copy');
  var errorEl = document.getElementById('url-error');

  function encode() {
    errorEl.textContent = '';
    try {
      outputEl.textContent = encodeURIComponent(inputEl.value);
    } catch(e) {
      errorEl.textContent = 'Error: ' + e.message;
    }
  }

  function decode() {
    errorEl.textContent = '';
    try {
      outputEl.textContent = decodeURIComponent(inputEl.value);
    } catch(e) {
      errorEl.textContent = 'Error: Invalid URL-encoded string';
    }
  }

  encodeBtn.addEventListener('click', encode);
  decodeBtn.addEventListener('click', decode);
  copyBtn.addEventListener('click', function() {
    window.uhCopy(outputEl.textContent);
  });
})();
</script>
"""

TOOL_SCRIPTS["color-picker"] = r"""
<script>
(function() {
  var colorInput = document.getElementById('cp-picker');
  var hexInput = document.getElementById('cp-hex');
  var rInput = document.getElementById('cp-r');
  var gInput = document.getElementById('cp-g');
  var bInput = document.getElementById('cp-b');
  var hInput = document.getElementById('cp-h');
  var sInput = document.getElementById('cp-s');
  var lInput = document.getElementById('cp-l');
  var previewEl = document.getElementById('cp-preview');

  function rgbToHex(r, g, b) {
    return '#' + [r, g, b].map(function(v) {
      return Math.round(v).toString(16).padStart(2, '0');
    }).join('');
  }

  function hexToRgb(hex) {
    var result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) } : null;
  }

  function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    var max = Math.max(r, g, b), min = Math.min(r, g, b);
    var h, s, l = (max + min) / 2;
    if (max === min) {
      h = s = 0;
    } else {
      var d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r: h = (g - b) / d + (g < b ? 6 : 0); break;
        case g: h = (b - r) / d + 2; break;
        case b: h = (r - g) / d + 4; break;
      }
      h /= 6;
    }
    return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
  }

  function hslToRgb(h, s, l) {
    h /= 360; s /= 100; l /= 100;
    var r, g, b;
    if (s === 0) {
      r = g = b = l;
    } else {
      var hue2rgb = function(p, q, t) {
        if (t < 0) t += 1;
        if (t > 1) t -= 1;
        if (t < 1/6) return p + (q - p) * 6 * t;
        if (t < 1/2) return q;
        if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
        return p;
      };
      var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      var p = 2 * l - q;
      r = hue2rgb(p, q, h + 1/3);
      g = hue2rgb(p, q, h);
      b = hue2rgb(p, q, h - 1/3);
    }
    return { r: Math.round(r * 255), g: Math.round(g * 255), b: Math.round(b * 255) };
  }

  function updateFromPicker() {
    var hex = colorInput.value;
    var rgb = hexToRgb(hex);
    if (!rgb) return;
    var hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    hexInput.value = hex;
    rInput.value = rgb.r;
    gInput.value = rgb.g;
    bInput.value = rgb.b;
    hInput.value = hsl.h;
    sInput.value = hsl.s;
    lInput.value = hsl.l;
    previewEl.style.backgroundColor = hex;
  }

  function updateFromRgb() {
    var r = parseInt(rInput.value) || 0;
    var g = parseInt(gInput.value) || 0;
    var b = parseInt(bInput.value) || 0;
    var hex = rgbToHex(r, g, b);
    var hsl = rgbToHsl(r, g, b);
    colorInput.value = hex;
    hexInput.value = hex;
    hInput.value = hsl.h;
    sInput.value = hsl.s;
    lInput.value = hsl.l;
    previewEl.style.backgroundColor = hex;
  }

  function updateFromHex() {
    var hex = hexInput.value;
    if (!/^#[0-9a-fA-F]{6}$/.test(hex)) return;
    var rgb = hexToRgb(hex);
    if (!rgb) return;
    var hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    colorInput.value = hex;
    rInput.value = rgb.r;
    gInput.value = rgb.g;
    bInput.value = rgb.b;
    hInput.value = hsl.h;
    sInput.value = hsl.s;
    lInput.value = hsl.l;
    previewEl.style.backgroundColor = hex;
  }

  function updateFromHsl() {
    var h = parseInt(hInput.value) || 0;
    var s = parseInt(sInput.value) || 0;
    var l = parseInt(lInput.value) || 0;
    var rgb = hslToRgb(h, s, l);
    var hex = rgbToHex(rgb.r, rgb.g, rgb.b);
    colorInput.value = hex;
    hexInput.value = hex;
    rInput.value = rgb.r;
    gInput.value = rgb.g;
    bInput.value = rgb.b;
    previewEl.style.backgroundColor = hex;
  }

  colorInput.addEventListener('input', updateFromPicker);
  hexInput.addEventListener('change', updateFromHex);
  [rInput, gInput, bInput].forEach(function(el) { el.addEventListener('input', updateFromRgb); });
  [hInput, sInput, lInput].forEach(function(el) { el.addEventListener('input', updateFromHsl); });

  updateFromPicker();
})();
</script>
"""

TOOL_SCRIPTS["timestamp-converter"] = r"""
<script>
(function() {
  var tsInput = document.getElementById('ts-input');
  var dateInput = document.getElementById('ts-date');
  var localEl = document.getElementById('ts-local');
  var utcEl = document.getElementById('ts-utc');
  var secondsEl = document.getElementById('ts-seconds');
  var msEl = document.getElementById('ts-ms');

  function formatDate(date) {
    return date.toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short' });
  }

  function updateFromTimestamp() {
    var ts = tsInput.value.trim();
    if (!ts) { localEl.textContent = '—'; utcEl.textContent = '—'; secondsEl.textContent = '—'; msEl.textContent = '—'; return; }
    var num = Number(ts);
    var ms = num.toString().length <= 10 ? num * 1000 : num;
    var date = new Date(ms);
    if (isNaN(date.getTime())) { localEl.textContent = 'Invalid timestamp'; utcEl.textContent = ''; return; }
    localEl.textContent = formatDate(date);
    utcEl.textContent = date.toUTCString();
    secondsEl.textContent = Math.floor(date.getTime() / 1000);
    msEl.textContent = date.getTime();
    // Set date input
    var iso = date.toISOString().substring(0, 16);
    dateInput.value = iso;
  }

  function updateFromDate() {
    var iso = dateInput.value;
    if (!iso) return;
    var date = new Date(iso);
    if (isNaN(date.getTime())) return;
    var seconds = Math.floor(date.getTime() / 1000);
    tsInput.value = seconds;
    localEl.textContent = formatDate(date);
    utcEl.textContent = date.toUTCString();
    secondsEl.textContent = seconds;
    msEl.textContent = date.getTime();
  }

  tsInput.addEventListener('input', updateFromTimestamp);
  dateInput.addEventListener('change', updateFromDate);

  // Set default to current time
  var now = Math.floor(Date.now() / 1000);
  tsInput.value = now;
  updateFromTimestamp();
})();
</script>
"""

TOOL_SCRIPTS["text-case-converter"] = r"""
<script>
(function() {
  var inputEl = document.getElementById('tc-input');
  var outputEl = document.getElementById('tc-output');
  var copyBtn = document.getElementById('tc-copy');
  var buttons = document.querySelectorAll('.tc-btn');

  function toSentenceCase(str) {
    return str.toLowerCase().replace(/(^\s*\w|[.!?]\s*\w)/g, function(c) { return c.toUpperCase(); });
  }
  function toTitleCase(str) {
    return str.toLowerCase().replace(/(?:^|\s)\S/g, function(c) { return c.toUpperCase(); });
  }
  function toCamelCase(str) {
    return str.toLowerCase().replace(/[^a-zA-Z0-9]+(.)/g, function(_, c) { return c.toUpperCase(); });
  }
  function toPascalCase(str) {
    var camel = toCamelCase(str);
    return camel.charAt(0).toUpperCase() + camel.slice(1);
  }
  function toSnakeCase(str) {
    return str.replace(/([a-z])([A-Z])/g, '$1_$2').replace(/[\s\-]+/g, '_').toLowerCase();
  }

  function convert(type) {
    var text = inputEl.value;
    switch(type) {
      case 'upper': outputEl.textContent = text.toUpperCase(); break;
      case 'lower': outputEl.textContent = text.toLowerCase(); break;
      case 'sentence': outputEl.textContent = toSentenceCase(text); break;
      case 'title': outputEl.textContent = toTitleCase(text); break;
      case 'camel': outputEl.textContent = toCamelCase(text); break;
      case 'pascal': outputEl.textContent = toPascalCase(text); break;
      case 'snake': outputEl.textContent = toSnakeCase(text); break;
    }
  }

  buttons.forEach(function(btn) {
    btn.addEventListener('click', function() { convert(this.dataset.type); });
  });
  copyBtn.addEventListener('click', function() {
    window.uhCopy(outputEl.textContent);
  });
})();
</script>
"""

TOOL_SCRIPTS["lorem-ipsum-generator"] = r"""
<script>
(function() {
  var countEl = document.getElementById('li-count');
  var unitEl = document.getElementById('li-unit');
  var outputEl = document.getElementById('li-output');
  var generateBtn = document.getElementById('li-generate');
  var copyBtn = document.getElementById('li-copy');

  var WORDS = 'lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur excepteur sint occaecat cupidatat non proident sunt in culpa qui officia deserunt mollit anim id est laborum'.split(' ');

  function randomWord() {
    return WORDS[Math.floor(Math.random() * WORDS.length)];
  }

  function generateSentence() {
    var len = 5 + Math.floor(Math.random() * 10);
    var words = [];
    for (var i = 0; i < len; i++) words.push(randomWord());
    var sentence = words.join(' ');
    return sentence.charAt(0).toUpperCase() + sentence.slice(1) + '.';
  }

  function generateParagraph() {
    var len = 3 + Math.floor(Math.random() * 4);
    var sentences = [];
    for (var i = 0; i < len; i++) sentences.push(generateSentence());
    return sentences.join(' ');
  }

  function generate() {
    var count = parseInt(countEl.value, 10) || 1;
    var unit = unitEl.value;
    var output = [];
    if (unit === 'paragraphs') {
      for (var i = 0; i < count; i++) output.push(generateParagraph());
      outputEl.innerHTML = output.join('<br><br>');
    } else if (unit === 'sentences') {
      for (var i = 0; i < count; i++) output.push(generateSentence());
      outputEl.innerHTML = output.join(' ');
    } else {
      var words = [];
      for (var i = 0; i < count; i++) words.push(randomWord());
      outputEl.textContent = words.join(' ');
    }
  }

  generateBtn.addEventListener('click', generate);
  copyBtn.addEventListener('click', function() {
    window.uhCopy(outputEl.textContent);
  });
  generate();
})();
</script>
"""

# Body HTML for each tool — the interactive UI
TOOL_BODY_HTML = {}

TOOL_BODY_HTML["word-counter"] = r"""
<div class="tool">
  <label for="wc-input">Paste or type your text</label>
  <textarea id="wc-input" placeholder="Start typing or paste your text here..."></textarea>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(10rem,1fr));gap:1rem;margin-top:1rem;padding:1rem;background:var(--panel-2);border-radius:8px;">
    <div><div style="font-size:1.5rem;font-weight:700;color:var(--accent);" id="wc-words">0</div><div style="color:var(--muted);font-size:.875rem;">Words</div></div>
    <div><div style="font-size:1.5rem;font-weight:700;color:var(--accent);" id="wc-chars">0</div><div style="color:var(--muted);font-size:.875rem;">Characters</div></div>
    <div><div style="font-size:1.5rem;font-weight:700;color:var(--accent);" id="wc-chars-ns">0</div><div style="color:var(--muted);font-size:.875rem;">Characters (no spaces)</div></div>
    <div><div style="font-size:1.5rem;font-weight:700;color:var(--accent);" id="wc-sentences">0</div><div style="color:var(--muted);font-size:.875rem;">Sentences</div></div>
    <div><div style="font-size:1.5rem;font-weight:700;color:var(--accent);" id="wc-paragraphs">0</div><div style="color:var(--muted);font-size:.875rem;">Paragraphs</div></div>
  </div>
</div>
"""

TOOL_BODY_HTML["password-generator"] = r"""
<div class="tool">
  <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem;">
    <label for="pg-length" style="margin:0;">Length: <span id="pg-length-val">16</span></label>
    <input type="range" id="pg-length" min="4" max="64" value="16" style="flex:1;">
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:1rem;margin-bottom:1rem;">
    <label><input type="checkbox" id="pg-upper" checked> Uppercase (A-Z)</label>
    <label><input type="checkbox" id="pg-lower" checked> Lowercase (a-z)</label>
    <label><input type="checkbox" id="pg-numbers" checked> Numbers (0-9)</label>
    <label><input type="checkbox" id="pg-symbols" checked> Symbols (!@#$...)</label>
  </div>
  <div style="display:flex;gap:.5rem;margin-bottom:1rem;">
    <button id="pg-generate" type="button">Generate Password</button>
    <button id="pg-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border);">Copy</button>
  </div>
  <div id="pg-output" style="font-family:monospace;font-size:1.25rem;padding:1rem;background:var(--panel-2);border-radius:8px;word-break:break-all;min-height:1.5rem;"></div>
</div>
"""

TOOL_BODY_HTML["unit-converter"] = r"""
<div class="tool">
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(12rem,1fr));gap:1rem;margin-bottom:1rem;">
    <div>
      <label for="uc-category">Category</label>
      <select id="uc-category">
        <option value="length">Length</option>
        <option value="weight">Weight</option>
        <option value="temperature">Temperature</option>
        <option value="volume">Volume</option>
        <option value="area">Area</option>
        <option value="speed">Speed</option>
        <option value="time">Time</option>
        <option value="data">Data Storage</option>
      </select>
    </div>
    <div>
      <label for="uc-from">From</label>
      <select id="uc-from"></select>
    </div>
    <div>
      <label for="uc-to">To</label>
      <select id="uc-to"></select>
    </div>
    <div>
      <label for="uc-input">Value</label>
      <input type="number" id="uc-input" placeholder="Enter value" step="any">
    </div>
  </div>
  <div style="padding:1.5rem;background:var(--panel-2);border-radius:8px;text-align:center;">
    <div style="color:var(--muted);font-size:.875rem;margin-bottom:.5rem;">Result</div>
    <div id="uc-result" style="font-size:2rem;font-weight:700;color:var(--accent);">—</div>
  </div>
</div>
"""

TOOL_BODY_HTML["json-formatter"] = r"""
<div class="tool">
  <label for="jf-input">Paste your JSON</label>
  <textarea id="jf-input" placeholder='Paste minified or pretty JSON here...'></textarea>
  <div style="display:flex;gap:.5rem;margin:.5rem 0 1rem;">
    <button id="jf-format" type="button">Format</button>
    <button id="jf-minify" type="button">Minify</button>
    <button id="jf-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border);">Copy</button>
  </div>
  <div id="jf-error" style="color:#ef4444;font-size:.875rem;margin-bottom:.5rem;"></div>
  <label>Output</label>
  <div id="jf-output" style="padding:1rem;background:var(--panel-2);border-radius:8px;font-family:monospace;white-space:pre-wrap;word-break:break-all;min-height:6rem;"></div>
</div>
"""

TOOL_BODY_HTML["base64-encoder-decoder"] = r"""
<div class="tool">
  <label for="b64-input">Enter text or Base64</label>
  <textarea id="b64-input" placeholder="Enter text to encode, or Base64 to decode..."></textarea>
  <div style="display:flex;gap:.5rem;margin:.5rem 0 1rem;">
    <button id="b64-encode" type="button">Encode to Base64</button>
    <button id="b64-decode" type="button">Decode from Base64</button>
    <button id="b64-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border);">Copy</button>
  </div>
  <div id="b64-error" style="color:#ef4444;font-size:.875rem;margin-bottom:.5rem;"></div>
  <label>Result</label>
  <div id="b64-output" style="padding:1rem;background:var(--panel-2);border-radius:8px;font-family:monospace;white-space:pre-wrap;word-break:break-all;min-height:6rem;"></div>
</div>
"""

TOOL_BODY_HTML["url-encoder-decoder"] = r"""
<div class="tool">
  <label for="url-input">Enter URL or text</label>
  <textarea id="url-input" placeholder="Enter URL to encode, or encoded URL to decode..."></textarea>
  <div style="display:flex;gap:.5rem;margin:.5rem 0 1rem;">
    <button id="url-encode" type="button">Encode URL</button>
    <button id="url-decode" type="button">Decode URL</button>
    <button id="url-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border);">Copy</button>
  </div>
  <div id="url-error" style="color:#ef4444;font-size:.875rem;margin-bottom:.5rem;"></div>
  <label>Result</label>
  <div id="url-output" style="padding:1rem;background:var(--panel-2);border-radius:8px;font-family:monospace;white-space:pre-wrap;word-break:break-all;min-height:6rem;"></div>
</div>
"""

TOOL_BODY_HTML["color-picker"] = r"""
<div class="tool">
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(10rem,1fr));gap:1rem;margin-bottom:1rem;">
    <div>
      <label for="cp-picker">Picker</label>
      <input type="color" id="cp-picker" value="#f59e0b" style="width:100%;height:3rem;padding:0;">
    </div>
    <div>
      <label for="cp-hex">Hex</label>
      <input type="text" id="cp-hex" value="#f59e0b" maxlength="7">
    </div>
    <div>
      <label>RGB</label>
      <div style="display:flex;gap:.5rem;">
        <input type="number" id="cp-r" min="0" max="255" placeholder="R" style="width:4rem;">
        <input type="number" id="cp-g" min="0" max="255" placeholder="G" style="width:4rem;">
        <input type="number" id="cp-b" min="0" max="255" placeholder="B" style="width:4rem;">
      </div>
    </div>
    <div>
      <label>HSL</label>
      <div style="display:flex;gap:.5rem;">
        <input type="number" id="cp-h" min="0" max="360" placeholder="H" style="width:4rem;">
        <input type="number" id="cp-s" min="0" max="100" placeholder="S" style="width:4rem;">
        <input type="number" id="cp-l" min="0" max="100" placeholder="L" style="width:4rem;">
      </div>
    </div>
  </div>
  <div id="cp-preview" style="height:4rem;border-radius:8px;border:1px solid var(--border);"></div>
</div>
"""

TOOL_BODY_HTML["timestamp-converter"] = r"""
<div class="tool">
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:1rem;margin-bottom:1rem;">
    <div>
      <label for="ts-input">Unix Timestamp</label>
      <input type="text" id="ts-input" placeholder="Enter seconds or milliseconds">
    </div>
    <div>
      <label for="ts-date">Date & Time</label>
      <input type="datetime-local" id="ts-date">
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:1rem;padding:1rem;background:var(--panel-2);border-radius:8px;">
    <div><div style="color:var(--muted);font-size:.875rem;">Local</div><div id="ts-local" style="font-weight:600;">—</div></div>
    <div><div style="color:var(--muted);font-size:.875rem;">UTC</div><div id="ts-utc" style="font-weight:600;">—</div></div>
    <div><div style="color:var(--muted);font-size:.875rem;">Seconds</div><div id="ts-seconds" style="font-weight:600;">—</div></div>
    <div><div style="color:var(--muted);font-size:.875rem;">Milliseconds</div><div id="ts-ms" style="font-weight:600;">—</div></div>
  </div>
</div>
"""

TOOL_BODY_HTML["text-case-converter"] = r"""
<div class="tool">
  <label for="tc-input">Paste your text</label>
  <textarea id="tc-input" placeholder="Type or paste text here..."></textarea>
  <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin:.5rem 0 1rem;">
    <button class="tc-btn" data-type="upper" type="button">UPPERCASE</button>
    <button class="tc-btn" data-type="lower" type="button">lowercase</button>
    <button class="tc-btn" data-type="sentence" type="button">Sentence case</button>
    <button class="tc-btn" data-type="title" type="button">Title Case</button>
    <button class="tc-btn" data-type="camel" type="button">camelCase</button>
    <button class="tc-btn" data-type="pascal" type="button">PascalCase</button>
    <button class="tc-btn" data-type="snake" type="button">snake_case</button>
    <button id="tc-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border);">Copy</button>
  </div>
  <label>Result</label>
  <div id="tc-output" style="padding:1rem;background:var(--panel-2);border-radius:8px;white-space:pre-wrap;word-break:break-all;min-height:6rem;"></div>
</div>
"""

TOOL_BODY_HTML["lorem-ipsum-generator"] = r"""
<div class="tool">
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(10rem,1fr));gap:1rem;margin-bottom:1rem;">
    <div>
      <label for="li-unit">Generate by</label>
      <select id="li-unit">
        <option value="paragraphs">Paragraphs</option>
        <option value="sentences">Sentences</option>
        <option value="words">Words</option>
      </select>
    </div>
    <div>
      <label for="li-count">Count</label>
      <input type="number" id="li-count" min="1" max="20" value="3">
    </div>
    <div style="display:flex;align-items:flex-end;">
      <button id="li-generate" type="button">Generate</button>
      <button id="li-copy" type="button" style="background:var(--panel-2);color:var(--fg);border-color:var(--border);">Copy</button>
    </div>
  </div>
  <label>Output</label>
  <div id="li-output" style="padding:1rem;background:var(--panel-2);border-radius:8px;min-height:6rem;line-height:1.8;"></div>
</div>
"""


def main():
    research = json.loads(RESEARCH.read_text(encoding="utf-8"))
    tools = research["tools"][:10]  # top 10 only

    config_tools = []
    for t in tools:
        slug = t["slug"]
        tool = {
            "slug": slug,
            "name": t["name"],
            "summary": SUMMARIES[slug],
            "title": t["seo"]["title"],
            "description": t["seo"]["description"],
            "h1": t["h1"],
            "intro": t["intro"],
            "faq": t["faq"],
            "how_it_works": t["how_it_works"],
            "body_html": TOOL_BODY_HTML[slug],
            "script": TOOL_SCRIPTS[slug],
        }
        config_tools.append(tool)

    config = {
        "$comment": "Single source of truth for the Utility Helpers site. Edit this file, then run `python3 scripts/build.py`. Tool entries added by UH-BUILD-TOOLS from Edith's UH-RESEARCH output.",
        "site": {
            "name": "Utility Helpers",
            "baseUrl": "https://utility-helpers.netlify.app",
            "tagline": "Free browser tools that run entirely on your device.",
            "description": "Free, fast, private browser tools. Every utility runs entirely in your browser — nothing is uploaded, nothing is stored, no account required.",
            "author": "Umang Mittal",
            "github": "https://github.com/umangm05/utility-helpers",
            "locale": "en_US",
            "themeColor": "#f59e0b"
        },
        "tools": config_tools
    }

    output = ROOT / "site.config.json"
    output.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(config_tools)} tools to {output}")


if __name__ == "__main__":
    main()
