"""Startup banner for the FEDS CLI.

Two renderings are shipped because a terminal that cannot encode U+2588 (the
Windows legacy console) turns the block logo into question marks:

* ``UNICODE_BANNER`` - ANSI-shadow block letters, what Gemini/Antigravity use.
* ``ASCII_BANNER``   - pure ASCII, identical on every terminal.

`pick_banner()` chooses automatically and can be overridden with
``FEDS_CLI_UNICODE=1`` (force blocks) or ``FEDS_CLI_UNICODE=0`` (force ASCII).
"""

from __future__ import annotations

import os
import sys

NAME = "FEDS"
TAGLINE = "Frontend Engineering Digital Specialist"
VENDOR = "By SangLabs"

UNICODE_BANNER = r"""
 ███████╗███████╗██████╗ ███████╗
 ██╔════╝██╔════╝██╔══██╗██╔════╝
 █████╗  █████╗  ██║  ██║███████╗
 ██╔══╝  ██╔══╝  ██║  ██║╚════██║
 ██║     ███████╗██████╔╝███████║
 ╚═╝     ╚══════╝╚═════╝ ╚══════╝
"""

ASCII_BANNER = r"""
 #####  #####  ####   ####
 #      #      #   #  #
 ####   ####   #   #   ###
 #      #      #   #     #
 #      #####  ####   ####
"""


def supports_unicode(file=None) -> bool:
    """True when the output stream can carry the block glyphs."""
    override = os.getenv("FEDS_CLI_UNICODE")
    if override is not None:
        return override.strip() not in {"0", "false", "no"}

    stream = file or sys.stdout
    encoding = (getattr(stream, "encoding", None) or "ascii").lower().replace("-", "")
    if encoding not in {"utf8", "utf16", "utf32"}:
        return False
    try:
        "█╔╝".encode(stream.encoding or "ascii")
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def logo(unicode: bool | None = None) -> str:
    """The block letters, sized to the caller's terminal."""
    if unicode is None:
        unicode = supports_unicode()
    return (UNICODE_BANNER if unicode else ASCII_BANNER).strip("\n")


def banner(version: str = "", unicode: bool | None = None) -> str:
    """Full startup card: logo, tagline, vendor, version."""
    lines = [logo(unicode), ""]
    padding = " " * 2
    lines.append(f"{padding}{TAGLINE}")
    lines.append(f"{padding}{VENDOR}")
    if version:
        lines.append("")
        lines.append(f"{padding}v{version}")
    return "\n".join(lines)
