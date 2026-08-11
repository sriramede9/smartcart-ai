import os
import sys
import time
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Path Setup: Add 'extract_from_flyers' to Python module path
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent if "__file__" in globals() else Path.cwd()
FLYER_DIR = BASE_DIR / "app" / "flyers"
OUTPUT_DIR = BASE_DIR / "output"
MODULE_DIR = BASE_DIR / "extract_from_flyers"

if str(MODULE_DIR) not in sys.path:
    sys.path.append(str(MODULE_DIR))

# Import pipeline modules
from pipeline import run_store, combine_stores
from google import genai
from google.genai import errors

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Gemini API Driver (Rate-limited for Free Tier compatibility)
# ---------------------------------------------------------------------------
def call_gemini(prompt: str) -> str:
    """
    Rate-limited Gemini 2.5 Flash driver function expected by normalizer.py.
    Paces requests to stay within the 15 RPM Free Tier ceiling.
    """
    client = genai.Client()
    
    # Pace calls: 4 seconds between requests = 15 calls/min max
    time.sleep(4) 

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return response.text
        except errors.APIError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"  ⚠️ Rate limit hit. Waiting 20s before retry ({attempt + 1}/3)...")
                time.sleep(20)
            else:
                raise e
    return "{}"


# ---------------------------------------------------------------------------
# Core Execution Function
# ---------------------------------------------------------------------------
def process_flyer(pdf_filename: str, store_name: str, mode: str = "regex", pages: list[int] | None = None) -> pd.DataFrame:
    """
    Processes a single flyer PDF through the SmartCart pipeline.
    
    mode: "regex" (free, fast offline testing) 
          "llm"   (Gemini API structured normalization)
    """
    pdf_path = FLYER_DIR / pdf_filename
    
    if not pdf_path.exists():
        print(f"❌ Error: Could not find '{pdf_filename}' in {FLYER_DIR}")
        return pd.DataFrame()

    print(f"\n==========================================")
    print(f" 🛒 SmartCart Processing: {store_name.upper()}")
    print(f" File: {pdf_filename} | Mode: {mode.upper()}")
    print(f"==========================================")

    call_llm_fn = call_gemini if mode == "llm" else None

    # Run Stage 0 -> Stage 1 -> Stage 2 -> DataFrame
    df = run_store(
        pdf_path=str(pdf_path),
        store=store_name,
        mode=mode,
        call_llm=call_llm_fn,
        pages=pages
    )

    print(f" Extracted {len(df)} structured products.")
    return df


# ---------------------------------------------------------------------------
# Main Runner Script
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # --- Mode Selection ---
    # Choose "regex" for quick local offline runs, or "llm" for Gemini API
    RUN_MODE = "regex" 

    # --- Step 1: Process FreshCo (Vector/Digital PDF) ---
    # Target Page 2 (0-indexed page index 1)
    df_freshco = process_flyer("flyer-freshco.pdf", store_name="freshco", mode=RUN_MODE, pages=[1])

    # --- Step 2: Save Extracted Dataset ---
    if not df_freshco.empty:
        csv_path = OUTPUT_DIR / f"freshco_products_{RUN_MODE}.csv"
        parquet_path = OUTPUT_DIR / f"freshco_products_{RUN_MODE}.parquet"

        df_freshco.to_csv(csv_path, index=False)
        print(f" Saved CSV -> {csv_path.name}")

        try:
            df_freshco.to_parquet(parquet_path, index=False)
            print(f" Saved Parquet -> {parquet_path.name}")
        except ImportError:
            print(" ⚠️ Note: Install 'pyarrow' via pip to enable Parquet file exports.")

        print("\n--- Sample Extracted Data ---")
        print(df_freshco[["product_name", "price", "unit", "page"]].head(10).to_string())