"""Карточки фидбека не должны иметь зашитый светлый фон: в тёмной теме текст становится нечитаемым."""
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "u2.css"


def _block(src: str, selector: str) -> str:
    i = src.find(selector)
    assert i != -1, selector
    return src[i:i + 400]


def test_jr_try_and_feedback_use_theme_tokens():
    css = CSS.read_text(encoding="utf-8")
    assert "#FFF4DE" not in css and "#FFD98A" not in css
    jr = _block(css, ".jr-try {")
    assert "color-mix(" in jr and "var(--mid)" in jr and "var(--card)" in jr
    assert "var(--text)" in jr
    assert "var(--mid-fg)" in _block(css, ".jr-try h2")
    res_ok = _block(css, ".u2-res.ok {")
    res_bad = _block(css, ".u2-res.bad {")
    assert "var(--good)" in res_ok and "var(--card)" in res_ok
    assert "var(--weak)" in res_bad and "var(--card)" in res_bad
    assert "--good-fg:" in css and "--weak-fg:" in css and "--mid-fg:" in css
    assert "var(--text)" in _block(css, ".th-again {")
    assert "var(--text)" in _block(css, ".th-offer {")
