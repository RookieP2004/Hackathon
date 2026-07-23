"""
fpdf2's built-in Helvetica/Times/Courier fonts are the base-14 PDF fonts --
WinAnsi/Latin-1 encoded, not Unicode. Real text flowing into these PDFs
(rag-service's real corpus citations, real document titles) legitimately
contains characters like em-dashes ("--" rendered as "—" in source
documents) that raise an uncaught FPDFException deep inside PDF generation.
That exception previously propagated all the way up through the Emergency
Agent's bus subscriber loop with no handler, silently killing its ability to
respond to every future critical assertion for the rest of the process's
life -- a real, previously-hidden production bug, not a hypothetical one.

Rather than bundling a Unicode TTF font, every PDF cell/multi_cell write in
this codebase should route through this sanitizer, which transliterates the
small set of "smart"/typographic Unicode punctuation real documents actually
contain into their plain-ASCII equivalents.
"""

from __future__ import annotations

_REPLACEMENTS = {
    "—": "--",  # em dash
    "–": "-",   # en dash
    "‘": "'", "’": "'",  # curly single quotes
    "“": '"', "”": '"',  # curly double quotes
    "…": "...",  # ellipsis
    " ": " ",  # non-breaking space
}


def sanitize_for_pdf(text: str) -> str:
    for unicode_char, ascii_equivalent in _REPLACEMENTS.items():
        text = text.replace(unicode_char, ascii_equivalent)
    return text.encode("latin-1", errors="replace").decode("latin-1")
