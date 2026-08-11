"""
End-to-end SmartCart flyer pipeline (Approach F).

    PDF -> extractor.extract_tokens()              (Stage 0: dual-path extraction)
        -> clustering.cluster_by_price_anchor()     (Stage 1: spatial clustering)
        -> normalizer.normalize_clusters()          (Stage 2: LLM / regex normalization)
        -> pandas.DataFrame                         (store, product_name, price, unit, ...)

Usage:
    python pipeline.py --pdf flyer-freshco.pdf --store freshco --mode regex
    python pipeline.py --pdf flyer-wallmart.pdf --store walmart --mode llm

Combine multiple stores:
    from pipeline import run_store, combine_stores
    df_fresh = run_store("flyer-freshco.pdf", "freshco", mode="llm")
    df_walmart = run_store("flyer-wallmart.pdf", "walmart", mode="llm")
    df = combine_stores([df_fresh, df_walmart])
    df.to_parquet("smartcart_products.parquet", index=False)
"""

from __future__ import annotations
import argparse
import pandas as pd

from extract_from_flyers.extractor import extract_tokens
from extract_from_flyers.clustering import cluster_by_price_anchor
from extract_from_flyers.normalizer import normalize_clusters, normalize_cluster_regex_fallback


def run_store(pdf_path: str, store: str, mode: str = "regex", call_llm=None,
              pages: list[int] | None = None) -> pd.DataFrame:
    """
    mode: "regex"  -> fast, free, zero-dependency first pass (normalizer.normalize_cluster_regex_fallback)
          "llm"    -> Stage 2 LLM normalization; requires `call_llm(prompt)->str`
    """
    tokens = extract_tokens(pdf_path, pages=pages)
    clusters = cluster_by_price_anchor(tokens)

    if mode == "regex":
        rows = [normalize_cluster_regex_fallback(c, store) for c in clusters]
        rows = [r for r in rows if r is not None]
    elif mode == "llm":
        if call_llm is None:
            raise ValueError("mode='llm' requires a call_llm(prompt: str) -> str function")
        rows = normalize_clusters(clusters, call_llm, store)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    df = pd.DataFrame(rows, columns=[
        "store", "product_name", "price", "unit", "size", "page", "source_raw_text"
    ])
    return df


def combine_stores(dfs: list[pd.DataFrame], dedup: bool = True) -> pd.DataFrame:
    combined = pd.concat(dfs, ignore_index=True)

    combined["product_name"] = combined["product_name"].str.strip()
    combined = combined[combined["price"] > 0]
    combined = combined[combined["price"] < 500]  # sanity ceiling; tune per-category later

    if dedup:
        combined = combined.drop_duplicates(subset=["store", "product_name", "price", "unit"])

    return combined.reset_index(drop=True)


def to_rag_documents(df: pd.DataFrame) -> list[dict]:
    """
    Flattens the DataFrame into RAG-ready text chunks, one per product,
    with metadata kept separate for filtering (store, price, unit) so the
    retriever can do hybrid structured+semantic search downstream.
    """
    docs = []
    for _, row in df.iterrows():
        unit_str = f" per {row['unit']}" if pd.notna(row.get("unit")) else ""
        size_str = f" ({row['size']})" if pd.notna(row.get("size")) else ""
        text = f"{row['product_name']}{size_str} — ${row['price']:.2f}{unit_str} at {row['store'].title()}"
        docs.append({
            "text": text,
            "metadata": {
                "store": row["store"],
                "product_name": row["product_name"],
                "price": float(row["price"]),
                "unit": row.get("unit"),
                "page": int(row["page"]),
            },
        })
    return docs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the SmartCart flyer pipeline on one PDF.")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--mode", choices=["regex", "llm"], default="regex")
    parser.add_argument("--out", default=None, help="output CSV path")
    args = parser.parse_args()

    df = run_store(args.pdf, args.store, mode=args.mode)
    print(df.to_string())

    out_path = args.out or f"{args.store}_products.csv"
    df.to_csv(out_path, index=False)
    print(f"\nSaved {len(df)} rows to {out_path}")
