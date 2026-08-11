"""
Stage 2 — LLM & Offline Regex Normalization (Approach F)
"""

from __future__ import annotations
import json
import re

SYSTEM_INSTRUCTIONS = """You are a data-extraction engine for grocery flyer text fragments.
You will be given a short, jumbled blob of OCR/PDF text pulled from around one price tag
on a flyer page. It may contain noise: "SAVE $X" badges, loyalty-card callouts, weight
ranges, unrelated nearby product fragments, or OCR garbage.

Return ONLY a JSON object (no markdown fences, no prose) with this exact shape:
{
  "valid": true | false,
  "product_name": string,   // clean product name, no promo text, no size/weight
  "price": number | null,   // the actual shelf/deal price as a float, e.g. 4.77
  "unit": string | null,    // e.g. "lb", "kg", "each", "100g", null if not present
  "size": string | null     // e.g. "375-500 g", null if not present
}

Rules:
- If the blob is pure noise / a promo badge with no identifiable product, set "valid": false
  and null out the other fields (except leave product_name as best guess or "").
- Never use a "SAVE $X" number as the price. Use the actual shelf/deal price given.
- Strip promotional words (SAVE, NEW, LIMIT, WOW, HOT) from product_name.
- If multiple prices appear, prefer the one that matches the anchor price you were given.
"""

PRICE_STRIP_RE = re.compile(r"[^\d.]")


def _build_prompt(cluster: dict, store: str) -> str:
    return (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"Store: {store}\n"
        f"Anchor price detected by spatial clustering: {cluster['price_text']}\n"
        f"Raw nearby text blob: \"{cluster['raw_text']}\"\n\n"
        f"JSON:"
    )


def _safe_parse_json(raw: str) -> dict | None:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None


def normalize_cluster(cluster: dict, call_llm, store: str) -> dict | None:
    """
    call_llm: callable(prompt: str) -> str   (raw model text response)
    Returns a clean row dict or None if the cluster was junk / unparseable.
    """
    prompt = _build_prompt(cluster, store)
    raw_response = call_llm(prompt)
    parsed = _safe_parse_json(raw_response)

    if not parsed or not parsed.get("valid"):
        return None
    if parsed.get("price") is None or not parsed.get("product_name"):
        return None

    return {
        "store": store,
        "product_name": str(parsed["product_name"]).strip(),
        "price": float(parsed["price"]),
        "unit": parsed.get("unit"),
        "size": parsed.get("size"),
        "page": cluster["page"],
        "source_raw_text": cluster["raw_text"],
    }


def normalize_clusters(clusters: list[dict], call_llm, store: str) -> list[dict]:
    rows = []
    for cluster in clusters:
        row = normalize_cluster(cluster, call_llm, store)
        if row is not None:
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Offline fallback: a zero-dependency regex normalizer for quick testing
# ---------------------------------------------------------------------------
NOISE_WORDS = {
    "save", "new", "limit", "wow", "hot", "was", "reg", "member", "price",
    "when", "you", "buy", "up", "to", "off", "card", "without", "scene+"
}
UNIT_RE = re.compile(r"/?(lb|kg|ea|each|100g|g|ml|pk)\b", re.IGNORECASE)


def normalize_cluster_regex_fallback(cluster: dict, store: str) -> dict | None:
    price_match = re.search(r"\$?(\d{1,2}\.\d{2})", cluster["price_text"])
    if not price_match:
        return None
    price = float(price_match.group(1))

    # Reject unreasonable prices for individual flyer items
    if price < 0.50 or price > 150.00:
        return None

    unit_match = UNIT_RE.search(cluster["raw_text"])
    unit = unit_match.group(1).lower() if unit_match else None

    text_without_unit = UNIT_RE.sub(" ", cluster["raw_text"])
    words = [
        w for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", text_without_unit)
        if w.lower() not in NOISE_WORDS and len(w) > 1
    ]
    
    # Cap product name to the first 6 meaningful words
    product_name = " ".join(words[:6]).strip()
    if not product_name or len(product_name) < 3:
        return None

    return {
        "store": store,
        "product_name": product_name,
        "price": price,
        "unit": unit,
        "size": None,
        "page": cluster["page"],
        "source_raw_text": cluster["raw_text"],
    }