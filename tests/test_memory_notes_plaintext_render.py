"""Regression tests for rendering agent-managed memory notes as plaintext.

Root cause: the memory panel rendered every section through ``renderMd()`` — the
full chat markdown renderer. The agent-managed notes (My Notes / User Profile /
Agent Soul) are *plaintext*, not markdown, and frequently contain literal
characters the renderer mangles: leading-asterisk tokens like ``*_TOKEN`` /
``*_KEY`` / ``*_SECRET`` (turned into stray ``<strong>``/``<em>`` runs), plus
apostrophes and backticks. The result on screen was garbled HTML such as
``<strong><em>`` fragments and ``&#39;`` artifacts, even though the on-disk
notes were clean.

Fix: render the three agent-notes sections (``memory``/``user``/``soul``)
verbatim via ``esc(content)`` inside a ``.memory-plaintext`` (``white-space:
pre-wrap``) container — true WYSIWYG with the edit textarea. ``project_context``
is a genuine markdown file (HERMES.md/AGENTS.md) and keeps markdown rendering.
"""
# (esc mirrored manually below)
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()
PANELS_JS = (REPO_ROOT / "static" / "panels.js").read_text(encoding="utf-8")
STYLE_CSS = (REPO_ROOT / "static" / "style.css").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Static source guarantees
# ---------------------------------------------------------------------------
def test_only_project_context_renders_markdown():
    body = re.search(
        r"function _memorySectionRendersMarkdown\(section\)\s*\{(.*?)\}",
        PANELS_JS,
        re.DOTALL,
    )
    assert body, "_memorySectionRendersMarkdown helper missing"
    inner = body.group(1)
    assert "project_context" in inner
    # The agent-managed plaintext sections must NOT opt into markdown rendering.
    for plaintext_section in ("'memory'", "'user'", "'soul'"):
        assert plaintext_section not in inner, (
            f"{plaintext_section} should not be markdown-rendered"
        )


def test_detail_render_gates_markdown_behind_helper():
    detail = re.search(
        r"function _renderMemoryDetail\(section\)\s*\{(.*?)\n\}",
        PANELS_JS,
        re.DOTALL,
    )
    assert detail, "_renderMemoryDetail not found"
    body = detail.group(1)
    # Markdown path is guarded by the helper, plaintext path escapes verbatim.
    assert "_memorySectionRendersMarkdown(section)" in body
    assert 'memory-plaintext">${esc(content)}' in body
    assert 'preview-md">${renderMd(content)}' in body


def test_plaintext_container_preserves_whitespace():
    assert ".memory-plaintext{" in STYLE_CSS
    rule = STYLE_CSS.split(".memory-plaintext{", 1)[1].split("}", 1)[0]
    assert "white-space:pre-wrap" in rule


# ---------------------------------------------------------------------------
# Behavioural mirror: esc() of a redactor-like note must not emit emphasis HTML
# ---------------------------------------------------------------------------
def _esc(s):
    # Faithful mirror of the WebUI esc() helper (static/ui.js:269):
    #   s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
    table = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}
    return "".join(table.get(c, c) for c in str(s if s is not None else ""))


REDACTOR_NOTE = (
    "Redactor masks secrets: *_TOKEN, *_KEY, *_SECRET and values like "
    "'sk-live-abc' or `Bearer xyz`. Don't log them."
)


def test_redactor_note_renders_verbatim_without_emphasis():
    rendered = _esc(REDACTOR_NOTE)
    # No emphasis tags should be introduced from the asterisks.
    assert "<strong>" not in rendered
    assert "<em>" not in rendered
    # The literal token markers survive intact (not consumed as markdown).
    assert "*_TOKEN" in rendered
    assert "*_KEY" in rendered
    assert "*_SECRET" in rendered
    # esc() encodes the apostrophe as &#39; in the HTML attribute-safe form, but
    # since the whole block is plaintext the browser shows the literal quote and
    # never re-processes it through the markdown entity-decode pass.
    assert "&#39;" in rendered
    assert "Don&#39;t log them." in rendered
