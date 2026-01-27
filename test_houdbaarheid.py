#!/usr/bin/env python3
"""
Lookup houdbaarheid-etikettekst (BBTCNR=118) + productnaam op basis van RVG nummer,
op basis van G-standaard fixed-width raw tekstbestanden.

Route:
BST004T (RVREGNR1 -> HPKODE + ATNMNR)
 -> BST351T (HPKODE -> BBETNR*)
 -> BST371T (filter BBETNR op BBTCNR == 118)
 -> BST362T (BBETNR -> BBETOM tekst)
En naam:
BST004T (ATNMNR) -> BST020T (NMNR -> NMNAAM)

Bestandslocatie (jouw situatie):
raw_data/g-standaard/BSTxxT  (alles in één map)

Belangrijk:
- RVG matching is leading-zero onafhankelijk:
  - input "012345" en "12345" matchen beide met "012345" in het bestand.
  - backend normaliseert door leading zeros te strippen voor de vergelijking.

Gebruik:
  python g_lookup_rvg.py --rvg 12345
  python g_lookup_rvg.py --rvg 012345
  python g_lookup_rvg.py --rvg 12345 --data-dir raw_data/g-standaard/BSTxxT
  python g_lookup_rvg.py --rvg 12345 --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


# -----------------------------
# Fixed-width helpers
# -----------------------------

def fw(line: str, start_1b: int, end_1b: int) -> str:
    """Slice fixed-width substring using 1-based inclusive positions."""
    return line[start_1b - 1:end_1b]


def norm(s: str) -> str:
    """Strip spaces only."""
    return s.strip()


def norm_intlike_strip_leading_zeros(s: str) -> str:
    """
    Normalize an int-like field for matching:
    - strip spaces
    - strip leading zeros
    - if result empty -> "0"
    Examples:
      "000123" -> "123"
      "  012345 " -> "12345"
      "000000" -> "0"
      "" -> ""
    """
    x = s.strip()
    if x == "":
        return ""
    x2 = x.lstrip("0")
    return x2 if x2 != "" else "0"


def safe_int(s: str) -> Optional[int]:
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def iter_lines(path: Path) -> Iterable[str]:
    """Yield lines from a file, stripping trailing newlines but keeping fixed-width spacing."""
    with path.open("r", encoding="latin-1", errors="replace") as f:
        for line in f:
            yield line.rstrip("\n\r")


# -----------------------------
# File discovery
# -----------------------------

def find_file(data_dir: Path, filename: str) -> Path:
    """
    Find a file named `filename` under data_dir (flat folder or tree).
    Also accepts common extensions.
    """
    candidates: List[Path] = []

    # direct
    direct = data_dir / filename
    if direct.exists():
        candidates.append(direct)

    # common extensions direct
    for ext in (".txt", ".dat", ".asc", ".csv"):
        p = data_dir / (filename + ext)
        if p.exists():
            candidates.append(p)

    # recursive (in case of subfolders)
    if not candidates:
        candidates.extend(data_dir.rglob(filename))
        for ext in (".txt", ".dat", ".asc", ".csv"):
            candidates.extend(data_dir.rglob(filename + ext))

    if not candidates:
        raise FileNotFoundError(f"Kon {filename} niet vinden onder {data_dir}")

    # Prefer shortest path
    candidates.sort(key=lambda p: (len(str(p)), str(p)))
    return candidates[0]


# -----------------------------
# Parsers / indices
# -----------------------------

def index_bst020_names(path_020: Path) -> Dict[str, str]:
    """
    BST020T: NMNR (006-012) -> NMNAAM (086-135)
    """
    nmnr_to_name: Dict[str, str] = {}
    for line in iter_lines(path_020):
        if len(line) < 135:
            continue
        nmnr = norm(fw(line, 6, 12))
        if not nmnr:
            continue
        nmnaam = fw(line, 86, 135).strip()
        if nmnaam:
            nmnr_to_name[nmnr] = nmnaam
    return nmnr_to_name


def index_bst351_hpk_to_bbetnr(path_351: Path) -> Dict[str, Set[str]]:
    """
    BST351T: HPKODE (006-013) -> set(BBETNR (022-025))
    """
    hpk_to_bbetnrs: Dict[str, Set[str]] = {}
    for line in iter_lines(path_351):
        if len(line) < 25:
            continue
        hpk = norm(fw(line, 6, 13))
        bbetnr = norm(fw(line, 22, 25))
        if not hpk or not bbetnr:
            continue
        hpk_to_bbetnrs.setdefault(hpk, set()).add(bbetnr)
    return hpk_to_bbetnrs


def index_bst371_bbetnr_to_categories(path_371: Path) -> Dict[str, Set[int]]:
    """
    BST371T: BBETNR (010-013) -> set(BBTCNR (006-009) as int)
    """
    bbetnr_to_cats: Dict[str, Set[int]] = {}
    for line in iter_lines(path_371):
        if len(line) < 13:
            continue
        bbtcnr = safe_int(fw(line, 6, 9))
        bbetnr = norm(fw(line, 10, 13))
        if bbtcnr is None or not bbetnr:
            continue
        bbetnr_to_cats.setdefault(bbetnr, set()).add(bbtcnr)
    return bbetnr_to_cats


def index_bst362_bbetnr_to_text(path_362: Path) -> Dict[str, str]:
    """
    BST362T: BBETNR (006-009) -> BBETOM (015-055)
    If multiple records exist for same BBETNR, keep last non-empty text seen.
    """
    bbetnr_to_text: Dict[str, str] = {}
    for line in iter_lines(path_362):
        if len(line) < 55:
            continue
        bbetnr = norm(fw(line, 6, 9))
        if not bbetnr:
            continue
        txt = fw(line, 15, 55).strip()
        if txt:
            bbetnr_to_text[bbetnr] = txt
    return bbetnr_to_text


def find_in_bst004_by_rvg(path_004: Path, rvg_input: str) -> List[Tuple[str, str, str, str]]:
    """
    BST004T: find rows where RVREGNR1 (302-307) matches RVG input, leading-zero independent.

    Return list of tuples: (hpkode, atnmnr, atkode, rvregnr1_raw)
      - HPKODE 014-021
      - ATNMNR 022-028
      - ATKODE 006-013
      - RVREGNR1 302-307 (raw from file)
    """
    want = norm_intlike_strip_leading_zeros(rvg_input)
    hits: List[Tuple[str, str, str, str]] = []

    for line in iter_lines(path_004):
        if len(line) < 307:
            continue

        rv_raw = norm(fw(line, 302, 307))
        if not rv_raw:
            continue

        rv_norm = norm_intlike_strip_leading_zeros(rv_raw)
        if rv_norm == want:
            hpk = norm(fw(line, 14, 21))
            atnmnr = norm(fw(line, 22, 28))
            atkode = norm(fw(line, 6, 13))
            hits.append((hpk, atnmnr, atkode, rv_raw))

    return hits


# -----------------------------
# Core lookup
# -----------------------------

def lookup_rvg(
    data_dir: Path,
    rvg: str,
    category: int = 118,
) -> Dict[str, object]:
    # Locate files
    p004 = find_file(data_dir, "BST004T")
    p020 = find_file(data_dir, "BST020T")
    p351 = find_file(data_dir, "BST351T")
    p371 = find_file(data_dir, "BST371T")
    p362 = find_file(data_dir, "BST362T")

    # Indices
    nmnr_to_name = index_bst020_names(p020)
    hpk_to_bbetnrs = index_bst351_hpk_to_bbetnr(p351)
    bbetnr_to_cats = index_bst371_bbetnr_to_categories(p371)
    bbetnr_to_text = index_bst362_bbetnr_to_text(p362)

    # Find products for RVG (leading-zero independent)
    rvg_in = rvg.strip()
    hits_004 = find_in_bst004_by_rvg(p004, rvg_in)

    results: List[Dict[str, object]] = []
    all_texts: List[str] = []
    all_names: Set[str] = set()

    for hpk, atnmnr, atkode, rv_raw in hits_004:
        name = nmnr_to_name.get(atnmnr, "")
        if name:
            all_names.add(name)

        bbetnrs = hpk_to_bbetnrs.get(hpk, set())
        bbetnrs_cat = [b for b in bbetnrs if category in bbetnr_to_cats.get(b, set())]

        texts: List[str] = []
        for b in sorted(set(bbetnrs_cat)):
            t = bbetnr_to_text.get(b, "")
            if t:
                texts.append(t)
                all_texts.append(t)

        results.append(
            {
                "rvg_input": rvg_in,
                "rvregnr1_in_file": rv_raw,
                "atkode": atkode,
                "hpkode": hpk,
                "atnmnr": atnmnr,
                "naam": name,
                "bbetnr_count_total_for_hpk": len(bbetnrs),
                "bbetnr_filtered_category": sorted(set(bbetnrs_cat)),
                "etikettekst_category_118": texts,
            }
        )

    # Deduplicate texts while preserving order
    seen: Set[str] = set()
    dedup_texts: List[str] = []
    for t in all_texts:
        if t not in seen:
            seen.add(t)
            dedup_texts.append(t)

    return {
        "query_rvg_input": rvg_in,
        "query_rvg_normalized": norm_intlike_strip_leading_zeros(rvg_in),
        "gevonden_records_in_bst004": len(hits_004),
        "namen": sorted(all_names),
        "houdbaarheid_etiketteksten_category_118": dedup_texts,
        "details_per_match": results,
        "files_used": {
            "BST004T": str(p004),
            "BST020T": str(p020),
            "BST351T": str(p351),
            "BST371T": str(p371),
            "BST362T": str(p362),
        },
    }


# -----------------------------
# CLI
# -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rvg", required=True, help="RVG/RVH nummer (leading zeros maken niet uit)")
    ap.add_argument(
        "--data-dir",
        default="raw_data/g-standaard",
        help="Directory met BSTxxT files (default: raw_data/g-standaard)",
    )
    ap.add_argument("--json", action="store_true", help="Print JSON output")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"data-dir bestaat niet: {data_dir}")

    out = lookup_rvg(data_dir=data_dir, rvg=args.rvg, category=118)

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    # Human-friendly output
    print(f"RVG query (input): {out['query_rvg_input']}")
    print(f"RVG query (normalized): {out['query_rvg_normalized']}")
    print(f"Gevonden records in BST004T: {out['gevonden_records_in_bst004']}")

    if out["namen"]:
        print("Naam/namen:")
        for n in out["namen"]:
            print(f"  - {n}")
    else:
        print("Naam/namen: (geen gevonden via BST020T)")

    print("\nHoudbaarheid etiketteksten (categorie 118):")
    texts = out["houdbaarheid_etiketteksten_category_118"]
    if not texts:
        print("  (geen teksten gevonden)")
    else:
        for i, t in enumerate(texts, 1):
            print(f"  {i}. {t}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
