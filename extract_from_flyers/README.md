# SmartCart Flyer Pipeline (Approach F)

Modules, in pipeline order:

1. **extractor.py** — Stage 0 (Approach C). Auto-detects vector vs scanned
   pages per PDF page (`char_count < 100` heuristic) and routes to
   `pdfplumber` or `pdf2image` + `pytesseract`. Outputs a unified token
   schema (`text, x0, top, x1, bottom, page, source, conf`) so downstream
   code never needs to know which extractor produced a token. OCR tokens
   are scaled from pixel space back into PDF point space so vector and OCR
   tokens share one coordinate system.

2. **clustering.py** — Stage 1 (Approach E). Two steps:
   - `merge_split_price_fragments`: fuses split big-callout prices (e.g. a
     large "4" + small "77" in separate bounding boxes) into one synthetic
     `$4.77` anchor token before anything else runs.
   - `cluster_by_price_anchor`: for each price anchor, pulls in nearby
     non-price tokens within a `140x90` px window, sorts them into natural
     reading order, and joins them into a raw text blob per product tile.

3. **normalizer.py** — Stage 2 (Approach F). Turns a messy blob like
   `"SAVE $2 4.77 Johnsonville Sausages 375-500 g /lb"` into structured
   JSON (`product_name, price, unit, size, valid`). Two modes:
   - `normalize_cluster_regex_fallback`: free, fast, zero-dependency first
     pass — good for smoke-testing extraction/clustering quality before
     spending on LLM calls.
   - `normalize_clusters(..., call_llm)`: the real Stage 2, decoupled from
     any specific SDK — pass in any `callable(prompt) -> str`.

4. **pipeline.py** — orchestrates all three stages per store PDF,
   combines multiple stores into one deduped DataFrame
   (`store, product_name, price, unit, size, page, source_raw_text`), and
   has `to_rag_documents()` to flatten rows into text+metadata chunks
   ready for embedding/retrieval.

## Verified so far
All three stages have been smoke-tested end-to-end on synthetic token
data (split-price fusion, multi-column clustering, regex normalization,
DataFrame assembly, RAG doc export) — all pass. **Not yet tested against
your real flyer PDFs**, since none were uploaded to this conversation.

## Next step
Upload `flyer-freshco.pdf`, `flyer-wallmart.pdf`, and the Food Basics PDF
and I'll run `extractor.py` against each to see what real token output
looks like (vector vs OCR routing, actual coordinate ranges), then tune
`RADIUS_DX/DY` and `FRAG_DX/DY` in clustering.py against real layouts —
the 140/90 and 40/35 windows here are reasonable starting guesses, not
calibrated numbers.

## Running

```bash
pip install pdfplumber pdf2image pytesseract pandas
# tesseract binary + poppler-utils also required on the system

python pipeline.py --pdf flyer-freshco.pdf --store freshco --mode regex
```

For the LLM stage, wire up `call_llm` with the Anthropic SDK — see the
docstring at the top of normalizer.py for the exact pattern.
