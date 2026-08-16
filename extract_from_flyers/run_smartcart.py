import os
import sys
import time
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Path Setup
# ---------------------------------------------------------------------------
# Path Setup
BASE_DIR = Path(__file__).parent.parent
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
# Gemini API Driver
# ---------------------------------------------------------------------------
def call_gemini(prompt: str) -> str:
    """
    Rate-limited Gemini 2.5 Flash driver function.

    Currently unused because RUN_MODE is set to 'regex'.
    """
    client = genai.Client()

    # Pace calls for Free Tier compatibility
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
                print(
                    f"  ⚠️ Rate limit hit. "
                    f"Waiting 20s before retry ({attempt + 1}/3)..."
                )
                time.sleep(20)
            else:
                raise e

    return "{}"


# ---------------------------------------------------------------------------
# Core Execution Function
# ---------------------------------------------------------------------------
def process_flyer(
    pdf_filename: str,
    store_name: str,
    mode: str = "regex",
    pages: list[int] | None = None,
) -> pd.DataFrame:

    pdf_path = FLYER_DIR / pdf_filename

    if not pdf_path.exists():
        print(f"❌ Error: Could not find '{pdf_filename}'")
        print(f"   Expected location: {pdf_path}")
        return pd.DataFrame()

    print("\n==========================================")
    print(f" 🛒 SmartCart Processing: {store_name.upper()}")
    print(f" File: {pdf_filename}")
    print(f" Mode: {mode.upper()}")
    print("==========================================")

    call_llm_fn = call_gemini if mode == "llm" else None

    df = run_store(
        pdf_path=str(pdf_path),
        store=store_name,
        mode=mode,
        call_llm=call_llm_fn,
        pages=pages,
    )

    print(f" Extracted {len(df)} structured products.")

    return df


# ---------------------------------------------------------------------------
# Main Runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":

    # ================================================================
    # MODE
    # ================================================================
    # Keep REGEX for now:
    #   - free
    #   - fast
    #   - no Gemini API calls
    #
    # Later we can switch this to "llm".
    # ================================================================
    RUN_MODE = "regex"


    # ================================================================
    # FOOD BASICS
    # ================================================================
    # Automatically find Food Basics flyers whose filename starts with:
    #
    #     FoodBasics Weekly Flyer
    #
    # Example:
    #
    #     FoodBasics Weekly Flyer - Last Week.pdf
    #     FoodBasics Weekly Flyer - This Week.pdf
    #
    # ================================================================

    foodbasics_files = sorted(
        FLYER_DIR.glob("FoodBasics Weekly Flyer*.pdf")
    )

    print("\n==========================================")
    print(" 🛒 SmartCart — Food Basics Runner")
    print("==========================================")

    if not foodbasics_files:
        print(
            "❌ No Food Basics flyers found.\n"
            f"   Looking in: {FLYER_DIR}\n"
            "   Expected filenames beginning with:\n"
            "   'FoodBasics Weekly Flyer'"
        )
        sys.exit(1)

    print(f"Found {len(foodbasics_files)} Food Basics flyer(s):")

    for flyer in foodbasics_files:
        print(f"  • {flyer.name}")

    print()


    # Process each Food Basics flyer
    for flyer_path in foodbasics_files:

        df_foodbasics = process_flyer(
            pdf_filename=flyer_path.name,
            store_name="foodbasics",
            mode=RUN_MODE,
        )

        if df_foodbasics.empty:
            print(f"⚠️ No products extracted from {flyer_path.name}")
            continue

        # ------------------------------------------------------------
        # Save output
        # ------------------------------------------------------------
        # Use the flyer filename as the base so multiple weeks
        # don't overwrite each other.
        # ------------------------------------------------------------

        safe_name = flyer_path.stem.replace(" ", "_")

        csv_path = OUTPUT_DIR / f"{safe_name}_{RUN_MODE}.csv"
        parquet_path = OUTPUT_DIR / f"{safe_name}_{RUN_MODE}.parquet"

        df_foodbasics.to_csv(csv_path, index=False)

        print(f" Saved CSV -> {csv_path.name}")

        try:
            df_foodbasics.to_parquet(
                parquet_path,
                index=False,
            )
            print(f" Saved Parquet -> {parquet_path.name}")

        except ImportError:
            print(
                " ⚠️ Note: Install 'pyarrow' to enable Parquet exports."
            )

        # ------------------------------------------------------------
        # Preview
        # ------------------------------------------------------------
        print("\n--- Sample Extracted Data ---")

        preview_columns = [
            col
            for col in [
                "product_name",
                "price",
                "unit",
                "page",
            ]
            if col in df_foodbasics.columns
        ]

        print(
            df_foodbasics[preview_columns]
            .head(10)
            .to_string(index=False)
        )

        print("\n")


    # ================================================================
    # FRESHCO — TEMPORARILY DISABLED
    # ================================================================
    #
    # Keeping this here so we don't forget it.
    # We will re-enable FreshCo after the Food Basics extraction
    # pipeline is understood and reasonably reliable.
    #
    # df_freshco = process_flyer(
    #     "flyer-freshco.pdf",
    #     store_name="freshco",
    #     mode=RUN_MODE,
    #     pages=[1],
    # )
    #
    # ================================================================


    print("==========================================")
    print(" ✅ Food Basics processing complete")
    print("==========================================")