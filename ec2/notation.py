"""Engineering notation: turns plain working text into markup with subscripts.

The same markup (<sub>, <sup>) is understood by browsers and by reportlab, so the web
report and the PDF show M₀₂, λlim, l₀ … identically.
"""
import re
from html import escape

# token: (base, subscript)
SYMBOLS = {
    "As,prov": ("A", "s,prov"), "As,req": ("A", "s,req"), "As,min": ("A", "s,min"),
    "As,max": ("A", "s,max"), "As": ("A", "s"), "Ac": ("A", "c"),
    "NRd,max": ("N", "Rd,max"), "NRd": ("N", "Rd"), "NEd": ("N", "Ed"),
    "MRdy": ("M", "Rdy"), "MRdz": ("M", "Rdz"), "MEdy": ("M", "Edy"), "MEdz": ("M", "Edz"),
    "MRd": ("M", "Rd"), "MEd": ("M", "Ed"), "M0Ed": ("M", "0Ed"), "M0e": ("M", "0e"),
    "M01": ("M", "01"), "M02": ("M", "02"), "M2": ("M", "2"),
    "Mtop": ("M", "top"), "Mbottom": ("M", "bottom"),
    "λlim": ("λ", "lim"), "l0,fi": ("l", "0,fi"), "l0": ("l", "0"),
    "fcd": ("f", "cd"), "fck": ("f", "ck"), "fyd": ("f", "yd"), "fyk": ("f", "yk"),
    "fctm": ("f", "ctm"), "fcm": ("f", "cm"), "Ecm": ("E", "cm"), "Es": ("E", "s"),
    "cnom,req": ("c", "nom,req"), "cnom": ("c", "nom"), "cmin,b": ("c", "min,b"),
    "Δcdev": ("Δc", "dev"), "φlink": ("φ", "link"), "φef": ("φ", "ef"),
    "Kφ": ("K", "φ"), "Kr": ("K", "r"), "e2": ("e", "2"), "ei": ("e", "i"),
    "ey": ("e", "y"), "ez": ("e", "z"), "rm": ("r", "m"), "nu": ("n", "u"), "nbal": ("n", "bal"),
    "dg": ("d", "g"), "d2": ("d", "2"), "bmin": ("b", "min"), "μfi": ("μ", "fi"),
    "γc": ("γ", "c"), "γs": ("γ", "s"), "αcc": ("α", "cc"), "εcu": ("ε", "cu"),
    "εyd": ("ε", "yd"), "εuk": ("ε", "uk"), "εc": ("ε", "c"), "σs": ("σ", "s"),
    "scl,max": ("s", "cl,max"), "i_s": ("i", "s"), "k1": ("k", "1"), "k2": ("k", "2"),
    # beams
    "VEd": ("V", "Ed"), "vEd": ("v", "Ed"), "vRd,max": ("v", "Rd,max"), "As2,req": ("A", "s2,req"),
    "As2": ("A", "s2"), "Asw": ("A", "sw"), "Asf": ("A", "sf"), "sf": ("s", "f"), "fsc": ("f", "sc"),
    "fywd": ("f", "ywd"), "gk": ("g", "k"), "qk": ("q", "k"), "Gk": ("G", "k"), "Qk": ("Q", "k"),
    "ψ0": ("ψ", "0"), "ψ2": ("ψ", "2"), "ρ0": ("ρ", "0"), "ρw,min": ("ρ", "w,min"),
    "beff,i": ("b", "eff,i"), "beff": ("b", "eff"), "bw": ("b", "w"), "hf": ("h", "f"),
    "sl,max": ("s", "l,max"), "st,max": ("s", "t,max"), "σsu": ("σ", "su"), "ΔFd": ("ΔF", "d"), "θf": ("θ", "f"),
}

_WORD = r"0-9A-Za-z_Ͱ-Ͽ"
_TOKEN = re.compile(
    rf"(?<![{_WORD}])("
    + "|".join(re.escape(t) for t in sorted(SYMBOLS, key=len, reverse=True))
    + rf")(?![{_WORD}])")
_POWER = re.compile(r"\^([0-9.]+|[a-z])")


def to_markup(text):
    """Escape text and add <sub>/<sup> for the symbols above and for ^powers."""
    out = escape(text, quote=False)
    out = _TOKEN.sub(lambda m: "{}<sub>{}</sub>".format(*SYMBOLS[m.group(1)]), out)
    return _POWER.sub(r"<sup>\1</sup>", out)


def plain(text):
    """Plain-text form (used for downloads and logs)."""
    return text.replace("i_s", "is")
