"""
Stage 1 — Price-Anchor Spatial Proximity Clustering (Flyer Integer Support)
"""

from __future__ import annotations
import re
import math

# 1. Explicit decimal prices ($5.77, 5.77)
EXPLICIT_PRICE_RE = re.compile(r"^\$?(\d{1,2}\.\d{2})$")

# 2. Flyer sale price integers (e.g. 177 -> $1.77, 577 -> $5.77, 1077 -> $10.77)
IMPLICIT_PRICE_RE = re.compile(r"^(\d{3,4})$")

# 3. Split price fragments ($5 + 77)
LONE_DOLLAR_RE = re.compile(r"^\$?\d{1,2}$")
LONE_CENTS_RE = re.compile(r"^\d{2}$")

NON_PRICE_UNITS = {
    "g", "g.", "ml", "ml.", "pk", "kg", "lb", "oz", "l", "ct", 
    "pts", "points", "pts.", "scene+", "scene", "litres", "litre",
    "roll", "rolls", "pack", "bags", "tubs", "tub", "bars"
}

NON_PRICE_PREFIXES = {
    "reg", "reg.", "regular", "was", "spend", "limit", "docket", "save", "save$", "about"
}

LEGAL_DISCLAIMER_KEYWORDS = {
    "privacy", "copyright", "jurisdiction", "trademark", "sobeys", "safeway"
}

FRAG_DX = 65
FRAG_DY = 40
RADIUS_DX = 140
RADIUS_DY = 90

def _center(tok: dict) -> tuple[float, float]:
    return ((tok["x0"] + tok["x1"]) / 2, (tok["top"] + tok["bottom"]) / 2)

def mark_non_price_tokens(tokens: list[dict]) -> list[dict]:
    """Flags tokens that are regular prices ('reg 7.49'), weights ('300 g'), or points ('150 pts')."""
    tokens = sorted(tokens, key=lambda t: (t["page"], t["top"], t["x0"]))
    n = len(tokens)
    
    for i in range(n):
        tok_text = tokens[i]["text"].lower().strip().rstrip(".,")
        
        # Check preceding token (e.g., 'reg 7.49', 'save $1.02')
        if i > 0:
            prev = tokens[i - 1]["text"].lower().strip().rstrip(".,")
            if prev in NON_PRICE_PREFIXES or prev.startswith("save"):
                tokens[i]["is_non_price"] = True
                
        # Check following token (e.g., '300 g', '150 pts', '12 pk')
        if i + 1 < n:
            nxt = tokens[i + 1]["text"].lower().strip().rstrip(".,")
            if nxt in NON_PRICE_UNITS or nxt in {"pts", "points", "when"}:
                tokens[i]["is_non_price"] = True
                
    return tokens

def format_implicit_price(text: str) -> str:
    """Converts flyer integers: '577' -> '$5.77', '1077' -> '$10.77'."""
    clean = text.replace("$", "").strip()
    if "." in clean:
        return f"${clean}"
    if len(clean) == 3:
        return f"${clean[0]}.{clean[1:]}"
    if len(clean) == 4:
        return f"${clean[:2]}.{clean[2:]}"
    return f"${clean}"

def merge_split_price_fragments(tokens: list[dict]) -> list[dict]:
    """Fuses split big-digit dollar + small cents fragments into synthetic price anchors."""
    tokens = mark_non_price_tokens(tokens)
    used = set()
    fused: list[dict] = []

    for i, dollar_tok in enumerate(tokens):
        if i in used or dollar_tok.get("is_non_price"):
            continue

        if not LONE_DOLLAR_RE.match(dollar_tok["text"]):
            continue

        dx0, dy0 = _center(dollar_tok)
        best_j, best_dist = None, float("inf")

        for j, cand in enumerate(tokens):
            if j == i or j in used or cand["page"] != dollar_tok["page"]:
                continue
            if cand.get("is_non_price"):
                continue

            if not LONE_CENTS_RE.match(cand["text"]):
                continue

            cx, cy = _center(cand)
            ddx, ddy = abs(cx - dx0), cy - dy0

            if ddx <= FRAG_DX and -20 <= ddy <= FRAG_DY:
                dist = math.hypot(ddx, ddy)
                if dist < best_dist:
                    best_dist, best_j = dist, j

        if best_j is not None:
            cents_tok = tokens[best_j]
            used.add(i)
            used.add(best_j)
            merged_text = f"${dollar_tok['text'].lstrip('$')}.{cents_tok['text']}"
            fused.append({
                "text": merged_text,
                "x0": min(dollar_tok["x0"], cents_tok["x0"]),
                "top": min(dollar_tok["top"], cents_tok["top"]),
                "x1": max(dollar_tok["x1"], cents_tok["x1"]),
                "bottom": max(dollar_tok["bottom"], cents_tok["bottom"]),
                "page": dollar_tok["page"],
                "source": "fused",
                "conf": None,
                "is_price_anchor": True,
            })

    leftover = [t for i, t in enumerate(tokens) if i not in used]
    return sorted(fused + leftover, key=lambda t: (t["page"], t["top"], t["x0"]))

def find_price_anchors(tokens: list[dict]) -> list[dict]:
    anchors = []
    for tok in tokens:
        if tok.get("is_non_price"):
            continue

        raw_text = tok["text"].strip()

        # Case A: Fused or Explicit Decimal Price ($5.77)
        if tok.get("is_price_anchor") or EXPLICIT_PRICE_RE.match(raw_text):
            a = dict(tok)
            a["is_price_anchor"] = True
            a["text"] = format_implicit_price(raw_text)
            anchors.append(a)

        # Case B: Implicit Flyer Sale Integer (377, 577, 1077)
        elif IMPLICIT_PRICE_RE.match(raw_text):
            a = dict(tok)
            a["is_price_anchor"] = True
            a["text"] = format_implicit_price(raw_text)
            anchors.append(a)

    return anchors

def cluster_by_price_anchor(tokens: list[dict], page_height: float = 1638.0, margin_top: float = 60.0, margin_bottom: float = 100.0) -> list[dict]:
    valid_tokens = [
        t for t in tokens 
        if t["top"] > margin_top and t["bottom"] < (page_height - margin_bottom)
    ]

    fused_tokens = merge_split_price_fragments(valid_tokens)
    anchors = find_price_anchors(fused_tokens)
    non_price_tokens = [t for t in fused_tokens if not t.get("is_price_anchor")]

    clusters = []
    for anchor in anchors:
        ax, ay = _center(anchor)
        nearby = []
        
        for tok in non_price_tokens:
            if tok["page"] != anchor["page"]:
                continue
            tx, ty = _center(tok)
            ddx, ddy = abs(tx - ax), abs(ty - ay)
            if ddx <= RADIUS_DX and ddy <= RADIUS_DY:
                nearby.append(tok)

        nearby.sort(key=lambda t: (round(t["top"] / 10), t["x0"]))
        raw_text = " ".join(t["text"] for t in nearby)

        words = raw_text.lower().split()
        if len(words) > 28 or any(w in LEGAL_DISCLAIMER_KEYWORDS for w in words):
            continue

        clusters.append({
            "page": anchor["page"],
            "price_text": anchor["text"],
            "anchor_bbox": (anchor["x0"], anchor["top"], anchor["x1"], anchor["bottom"]),
            "raw_text": raw_text,
            "tokens": nearby,
        })

    return clusters