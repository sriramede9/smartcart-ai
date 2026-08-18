"""
SmartCart Data Collection Engine
Target: M6P 0C2 (Junction Triangle, Toronto)
Description: Ingests all active grocery flyer items from Flipp/Wishabi,
             normalizes prices, and exports master and per-store CSVs.
"""

import glob
import os
import re
import sys
from typing import Any, Dict, List, Optional
import pandas as pd
import requests

# ==========================================================
# CONFIGURATION
# ==========================================================
POSTAL_CODE = "M6P0C2"
LOCALE = "en-ca"
BASE_URL = "https://backflipp.wishabi.com/flipp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

TARGET_MERCHANTS = [
    "food basics",
    "no frills",
    "freshco",
    "walmart",
    "loblaws",
    "metro",
    "fiesta farms",
    "giant tiger",
    "nations",
    "t&t supermarket",
    "galleria",
    "bulk barn",
    "shoppers drug mart",
    "costco"
]

OUTPUT_DIR = "grocery_data_M6P0C2"


# ==========================================================
# API FETCHER FUNCTIONS
# ==========================================================
def get_all_flyers(postal_code: str) -> List[Dict[str, Any]]:
    """Retrieve all available flyer metadata for the postal code."""
    url = f"{BASE_URL}/flyers"
    params = {"postal_code": postal_code.replace(" ", "").upper(), "locale": LOCALE}
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=12)
        res.raise_for_status()
        return res.json().get("flyers", [])
    except Exception as e:
        print(f"[-] Error fetching flyer index: {e}", file=sys.stderr)
        return []


def get_flyer_items(flyer_id: int, postal_code: str) -> List[Dict[str, Any]]:
    """Retrieve complete item payload for a specific flyer ID without search caps."""
    url = f"{BASE_URL}/flyers/{flyer_id}"
    params = {"postal_code": postal_code.replace(" ", "").upper(), "locale": LOCALE}
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            return data.get("items") or data.get("flyer_items") or []
    except Exception:
        pass
    return []


def fallback_search_items(merchant_name: str, postal_code: str) -> List[Dict[str, Any]]:
    """Fallback search in case a merchant's items are only indexed via search."""
    url = f"{BASE_URL}/items/search"
    params = {
        "postal_code": postal_code.replace(" ", "").upper(),
        "q": merchant_name,
        "locale": LOCALE,
    }
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=12)
        if res.status_code == 200:
            return res.json().get("items", [])
    except Exception:
        pass
    return []


# ==========================================================
# PARSING & EXTRACTION HELPERS
# ==========================================================
def extract_price_value(item: Dict[str, Any]) -> Optional[float]:
    """Safely extracts numeric price from explicit fields or text badges."""
    for key in ["price", "current_price", "sale_price", "final_price"]:
        val = item.get(key)
        if val is not None:
            try:
                num = float(str(val).replace("$", "").replace(",", "").strip())
                if num > 0:
                    return num
            except ValueError:
                pass

    # Regex fallback from text strings (e.g., "$3.99 /lb", "SAVE $2.00", "2 FOR $5")
    for text_key in ["pre_price_text", "post_price_text", "sale_story", "description", "name"]:
        txt = str(item.get(text_key) or "")
        match = re.search(r"\$\s*(\d+(\.\d{1,2})?)", txt)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
    return None


def extract_name(item: Dict[str, Any]) -> str:
    """Extracts product title across variable schema representations."""
    for key in ["name", "clean_name", "display_name", "item_name", "title", "description"]:
        val = item.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return "Unknown Item"


# ==========================================================
# MAIN EXECUTION
# ==========================================================
def run_pipeline():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[*] Discovering active flyers for {POSTAL_CODE}...")

    flyers = get_all_flyers(POSTAL_CODE)
    matched_flyers = [
        f
        for f in flyers
        if any(target in (f.get("merchant_name") or f.get("merchant") or "").lower() for target in TARGET_MERCHANTS)
    ]

    print(f"[+] Found {len(flyers)} total flyers; {len(matched_flyers)} match target grocery merchants.\n")

    all_records = []

    for f in matched_flyers:
        flyer_id = f.get("id")
        merchant = f.get("merchant_name") or f.get("merchant")
        valid_from = f.get("valid_from")
        valid_to = f.get("valid_to")

        items = get_flyer_items(flyer_id, POSTAL_CODE)
        if not items:
            items = fallback_search_items(merchant, POSTAL_CODE)

        print(f" • {merchant:<24} (Flyer #{flyer_id:<8}): {len(items):>4} raw items")

        for item in items:
            name = extract_name(item)
            price_val = extract_price_value(item)
            orig_price = item.get("original_price")
            pre_text = item.get("pre_price_text") or ""
            post_text = item.get("post_price_text") or ""
            brand = item.get("brand") or ""

            display_price = (
                f"{pre_text} ${price_val} {post_text}".strip()
                if price_val is not None
                else (pre_text or post_text or "")
            )

            all_records.append({
                "store": merchant,
                "flyer_id": flyer_id,
                "item_id": item.get("flyer_item_id") or item.get("id"),
                "name": name,
                "brand": brand.strip(),
                "price": price_val,
                "original_price": orig_price,
                "pre_price_text": pre_text,
                "post_price_text": post_text,
                "display_price": display_price,
                "sale_story": item.get("sale_story") or "",
                "valid_from": item.get("valid_from") or valid_from,
                "valid_to": item.get("valid_to") or valid_to,
                "page_number": item.get("page_number") or item.get("page"),
                "left": item.get("left"),
                "top": item.get("top"),
                "right": item.get("right"),
                "bottom": item.get("bottom"),
                "cutout_image_url": item.get("cutout_image_url") or item.get("clean_image_url") or item.get("image_url"),
            })

    df = pd.DataFrame(all_records)
    if df.empty:
        print("[-] Error: No items extracted.", file=sys.stderr)
        return

    # Data formatting and deduplication
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["original_price"] = pd.to_numeric(df["original_price"], errors="coerce")
    df.dropna(subset=["name"], inplace=True)
    df.drop_duplicates(subset=["store", "name", "price", "valid_to"], inplace=True)
    df.sort_values(by=["store", "name"], inplace=True)

    # 1. Export Master CSV
    master_path = os.path.join(OUTPUT_DIR, f"master_grocery_deals_{POSTAL_CODE}.csv")
    df.to_csv(master_path, index=False)

    # 2. Export Individual Store CSVs
    for store_name, group_df in df.groupby("store"):
        clean_filename = (
            "".join(c for c in store_name if c.isalnum() or c in (" ", "_"))
            .rstrip()
            .replace(" ", "_")
            .lower()
        )
        store_csv_path = os.path.join(OUTPUT_DIR, f"{clean_filename}.csv")
        group_df.to_csv(store_csv_path, index=False)

    print("\n" + "=" * 70)
    print("EXTRACTION COMPLETE - DISK AUDIT")
    print("=" * 70)

    # Verify generated CSV files on disk
    files = glob.glob(f"{OUTPUT_DIR}/*.csv")
    summary = []
    for f in sorted(files):
        f_df = pd.read_csv(f)
        summary.append({
            "File": os.path.basename(f),
            "Total Rows": len(f_df),
            "Priced Rows": f_df["price"].notna().sum(),
            "Null Price %": f"{(f_df['price'].isna().mean() * 100):.1f}%",
            "Unique Brands": f_df["brand"].dropna().replace("", pd.NA).dropna().nunique(),
        })

    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    run_pipeline()