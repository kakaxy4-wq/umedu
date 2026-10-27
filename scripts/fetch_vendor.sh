#!/usr/bin/env bash
# Скачивает Pyodide (Python для браузера) и редактор CodeMirror в app/static/vendor.
# Всё хранится на своём сервере: страница изолирована (COOP/COEP), чужие CDN не нужны.
set -euo pipefail

PYODIDE_VERSION="0.26.4"
CODEMIRROR_VERSION="5.65.21"
FONTSOURCE_VERSION="5.3.0"
REGISTRY="https://registry.npmjs.org"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/app/static/vendor"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$VENDOR/pyodide" "$VENDOR/codemirror" "$VENDOR/fonts"

if [ ! -f "$VENDOR/pyodide/.version" ] || [ "$(cat "$VENDOR/pyodide/.version")" != "$PYODIDE_VERSION" ]; then
    echo "→ Pyodide $PYODIDE_VERSION"
    curl -fsSL "$REGISTRY/pyodide/-/pyodide-$PYODIDE_VERSION.tgz" -o "$TMP/pyodide.tgz"
    tar -xzf "$TMP/pyodide.tgz" -C "$TMP"
    for f in pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip pyodide-lock.json; do
        cp "$TMP/package/$f" "$VENDOR/pyodide/"
    done
    echo "$PYODIDE_VERSION" > "$VENDOR/pyodide/.version"
else
    echo "✓ Pyodide $PYODIDE_VERSION уже скачан"
fi

if [ ! -f "$VENDOR/codemirror/.version" ] || [ "$(cat "$VENDOR/codemirror/.version")" != "$CODEMIRROR_VERSION" ]; then
    echo "→ CodeMirror $CODEMIRROR_VERSION"
    curl -fsSL "$REGISTRY/codemirror/-/codemirror-$CODEMIRROR_VERSION.tgz" -o "$TMP/cm.tgz"
    tar -xzf "$TMP/cm.tgz" -C "$TMP"
    cp "$TMP/package/lib/codemirror.js" "$TMP/package/lib/codemirror.css" "$VENDOR/codemirror/"
    cp "$TMP/package/mode/python/python.js" "$VENDOR/codemirror/"
    cp "$TMP/package/addon/edit/matchbrackets.js" "$TMP/package/addon/edit/closebrackets.js" "$VENDOR/codemirror/"
    echo "$CODEMIRROR_VERSION" > "$VENDOR/codemirror/.version"
else
    echo "✓ CodeMirror $CODEMIRROR_VERSION уже скачан"
fi

FONTS="golos-text jetbrains-mono unbounded"
if [ ! -f "$VENDOR/fonts/.version" ] || [ "$(cat "$VENDOR/fonts/.version")" != "$FONTSOURCE_VERSION $FONTS" ]; then
    echo "→ Шрифты Golos Text, JetBrains Mono и Unbounded (fontsource $FONTSOURCE_VERSION)"
    rm -f "$VENDOR/fonts/"*.woff2
    for font in $FONTS; do
        curl -fsSL "$REGISTRY/@fontsource-variable/$font/-/$font-$FONTSOURCE_VERSION.tgz" -o "$TMP/$font.tgz"
        mkdir -p "$TMP/$font" && tar -xzf "$TMP/$font.tgz" -C "$TMP/$font"
        for sub in cyrillic latin; do
            cp "$TMP/$font/package/files/$font-$sub-wght-normal.woff2" "$VENDOR/fonts/"
        done
    done
    echo "$FONTSOURCE_VERSION $FONTS" > "$VENDOR/fonts/.version"
else
    echo "✓ Шрифты уже скачаны"
fi

echo "Готово: $VENDOR"
