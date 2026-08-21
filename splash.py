#!/usr/bin/env python3
"""Reusable startup splash: a teal-to-navy gradient banner plus a VK credit badge.

Drop this file into any repo and print it from your setup script or bootstrap:

    python3 splash.py                      # AutoMDConvert's AUTO MD banner
    python3 splash.py "PROJECTOMAC"        # any project name, styled generically
    python3 splash.py "MY TOOL" "does the thing, automatically"

From Python:
    from splash import render
    render()                               # default AUTO MD banner + credit
    render("My Tool", "a short tagline")   # any title

Environment:
    SPLASH_OFF=1        skip the splash entirely (also honors AUTOMDCONVERT_NO_SPLASH)
    SPLASH_PLAIN_VK=1   use a plain "VK" instead of the styled glyph (also honors
                        AUTOMDCONVERT_PLAIN_VK), for terminals without fancy fonts

Stdlib only. Truecolor ANSI; renders in VS Code and modern terminals.
"""

from __future__ import annotations

import os
import sys

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

TEAL = (45, 212, 191)   # gradient top
NAVY = (30, 58, 138)    # gradient bottom
BRK = (59, 130, 246)    # blue corner brackets
LTR = (147, 197, 253)   # light-blue VK
CREDIT_NAME = "VK"

# Block art for the built-in "AUTO MD" title (AutoMDConvert's hero banner).
_BLOCK = [
    " █████╗ ██╗   ██╗████████╗ ██████╗    ███╗   ███╗██████╗ ",
    "██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗   ████╗ ████║██╔══██╗",
    "███████║██║   ██║   ██║   ██║   ██║   ██╔████╔██║██║  ██║",
    "██╔══██║██║   ██║   ██║   ██║   ██║   ██║╚██╔╝██║██║  ██║",
    "██║  ██║╚██████╔╝   ██║   ╚██████╔╝   ██║ ╚═╝ ██║██████╔╝",
    "╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝    ╚═╝     ╚═╝╚═════╝ ",
]
_DEFAULT_TAGLINE = "documents in, clean Markdown out, automatically"


def _rgb(c) -> str:
    return f"\033[38;2;{c[0]};{c[1]};{c[2]}m"


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _block_banner() -> None:
    n = len(_BLOCK)
    for i, line in enumerate(_BLOCK):
        print(_rgb(_lerp(TEAL, NAVY, i / (n - 1))) + BOLD + line + RESET)


def _text_banner(title: str) -> None:
    """Portable banner for any title: letter-spaced caps with a horizontal gradient."""
    chars = list(title.upper())
    spaced = "  ".join(chars)
    out = []
    n = max(1, len(spaced) - 1)
    for i, ch in enumerate(spaced):
        out.append(_rgb(_lerp(TEAL, NAVY, i / n)) + BOLD + ch + RESET)
    print("  " + "".join(out))
    print("  " + _rgb(NAVY) + "─" * len(spaced) + RESET)


def _credit() -> None:
    plain = os.environ.get("SPLASH_PLAIN_VK") or os.environ.get("AUTOMDCONVERT_PLAIN_VK")
    mono = "VK" if plain else "𝗩𝗞"
    badge = f"{_rgb(BRK)}「{RESET} {_rgb(LTR)}{BOLD}{mono}{RESET} {_rgb(BRK)}」{RESET}"
    print(f"        {badge}   {DIM}crafted by {CREDIT_NAME}{RESET}")


def render(title: str | None = None, tagline: str | None = None, credit: bool = True) -> None:
    """Print the splash. title=None uses the built-in AUTO MD banner."""
    if os.environ.get("SPLASH_OFF") or os.environ.get("AUTOMDCONVERT_NO_SPLASH"):
        return
    print()
    if title is None:
        _block_banner()
        if tagline is None:
            tagline = _DEFAULT_TAGLINE
    else:
        _text_banner(title)
    if tagline:
        print(DIM + "        " + tagline + RESET)
    print()
    if credit:
        _credit()
        print()


if __name__ == "__main__":
    args = sys.argv[1:]
    render(args[0] if len(args) > 0 else None, args[1] if len(args) > 1 else None)
