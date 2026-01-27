#!/usr/bin/env python3
"""
Vult lookup.db aan met G-standaard tabellen voor:
RVG -> (HPKODE, ATNMNR) -> BBETNR -> (BBTCNR=118) -> BBETOM
en ATNMNR -> NMNAAM.

Leest fixed-width BST files uit:
raw_data/g-standaard/

Toegevoegde tabellen:
- g_bst004_articles
- g_bst020_names
- g_bst351_hpk_bbetnr
- g_bst371_bbetnr_category
- g_bst362_bbetnr_text

Gebruik:
  python util/import_g_houdbaarheid_to_lookup.py
  python util/import_g_houdbaarheid_to_lookup.py --category 118
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


# -----------------------------
# Pad configuratie (zelfde stijl als jouw util)
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE_DIR, "raw_data", "g-standaard")
DB_PATH = os.path.join(BASE_DIR, "lookup.db")


# -----------------------------
# Fixed-width helpers
# -----------------------------
def fw(line: str, start_1b: int, end_1b: int) -> str:
    return line[start_1b - 1 : end_1b]


def norm(s: str) -> str:
    return s.strip()


def norm_intlike_strip_leading_zeros(s: str) -> str:
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
    with path.open("r", encoding="latin-1", errors="replace") as f:
        for line in f:
            yield line.rstrip("\n\r")


# -----------------------------
# File discovery
# -----------------------------
def find_file(raw_dir: Path, filename: str) -> Path:
    """
    Zoek bestand exact, of met extension (txt/dat/asc/csv) in RAW_DIR.
    """
    direct = raw_dir / filename
    if direct.exists():
        return direct

    for ext in (".txt", ".dat", ".asc", ".csv"):
        p = raw_dir / (filename + ext)
        if p.exists():
            return p

    raise FileNotFoundError(f"Kon {filename} niet vinden in {raw_dir}")


# -----------------------------
# DB schema
# -----------------------------
def ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # BST004T: relevante velden voor route
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS g_bst004_articles (
            rvg_norm   TEXT NOT NULL,      -- RVREGNR1 normalized (leading zeros stripped)
            rvg_raw    TEXT,               -- RVREGNR1 raw as in file
            atkode     TEXT,               -- ATKODE (006-013)
            hpkode     TEXT,               -- HPKODE (014-021)
            atnmnr     TEXT,               -- ATNMNR (022-028)
            PRIMARY KEY (rvg_norm, hpkode, atnmnr, atkode)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_g004_rvg_norm ON g_bst004_articles(rvg_norm)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_g004_hpk ON g_bst004_articles(hpkode)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_g004_atnmnr ON g_bst004_articles(atnmnr)")

    # BST020T: naam
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS g_bst020_names (
            nmnr   TEXT PRIMARY KEY,       -- NMNR (006-012)
            nmnaam TEXT                    -- NMNAAM (086-135)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_g020_nmnaam ON g_bst020_names(nmnaam)")

    # BST351T: HPKODE -> BBETNR
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS g_bst351_hpk_bbetnr (
            hpkode TEXT NOT NULL,          -- HPKODE (006-013)
            bbetnr TEXT NOT NULL,          -- BBETNR (022-025)
            PRIMARY KEY (hpkode, bbetnr)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_g351_hpk ON g_bst351_hpk_bbetnr(hpkode)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_g351_bbetnr ON g_bst351_hpk_bbetnr(bbetnr)")

    # BST371T: BBETNR -> BBTCNR
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS g_bst371_bbetnr_category (
            bbetnr TEXT NOT NULL,          -- BBETNR (010-013)
            bbtcnr INTEGER NOT NULL,       -- BBTCNR (006-009)
            PRIMARY KEY (bbetnr, bbtcnr)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_g371_bbtcnr ON g_bst371_bbetnr_category(bbtcnr)")

    # BST362T: BBETNR -> BBETOM
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS g_bst362_bbetnr_text (
            bbetnr TEXT PRIMARY KEY,       -- BBETNR (006-009)
            bbetom TEXT                    -- BBETOM (015-055)
        )
        """
    )

    conn.commit()


# -----------------------------
# Parsers -> DB inserts
# -----------------------------
def parse_bst004(conn: sqlite3.Connection, path_004: Path) -> int:
    """
    BST004T:
      ATKODE 006-013
      HPKODE 014-021
      ATNMNR 022-028
      RVREGNR1 302-307
    """
    cur = conn.cursor()
    batch: List[Tuple[str, str, str, str, str]] = []
    count = 0

    for line in iter_lines(path_004):
        if len(line) < 307:
            continue

        atkode = norm(fw(line, 6, 13))
        hpkode = norm(fw(line, 14, 21))
        atnmnr = norm(fw(line, 22, 28))
        rvg_raw = norm(fw(line, 302, 307))
        if not rvg_raw or not hpkode or not atnmnr:
            continue

        rvg_norm = norm_intlike_strip_leading_zeros(rvg_raw)
        if not rvg_norm:
            continue

        batch.append((rvg_norm, rvg_raw, atkode, hpkode, atnmnr))
        count += 1

        if len(batch) >= 50000:
            cur.executemany(
                """
                INSERT OR IGNORE INTO g_bst004_articles
                (rvg_norm, rvg_raw, atkode, hpkode, atnmnr)
                VALUES (?, ?, ?, ?, ?)
                """,
                batch,
            )
            conn.commit()
            batch.clear()

    if batch:
        cur.executemany(
            """
            INSERT OR IGNORE INTO g_bst004_articles
            (rvg_norm, rvg_raw, atkode, hpkode, atnmnr)
            VALUES (?, ?, ?, ?, ?)
            """,
            batch,
        )
        conn.commit()

    return count


def parse_bst020(conn: sqlite3.Connection, path_020: Path) -> int:
    """
    BST020T:
      NMNR 006-012
      NMNAAM 086-135
    """
    cur = conn.cursor()
    batch: List[Tuple[str, str]] = []
    count = 0

    for line in iter_lines(path_020):
        if len(line) < 135:
            continue
        nmnr = norm(fw(line, 6, 12))
        nmnaam = fw(line, 86, 135).strip()
        if not nmnr or not nmnaam:
            continue
        batch.append((nmnr, nmnaam))
        count += 1

        if len(batch) >= 50000:
            cur.executemany(
                "INSERT OR IGNORE INTO g_bst020_names (nmnr, nmnaam) VALUES (?, ?)",
                batch,
            )
            conn.commit()
            batch.clear()

    if batch:
        cur.executemany(
            "INSERT OR IGNORE INTO g_bst020_names (nmnr, nmnaam) VALUES (?, ?)",
            batch,
        )
        conn.commit()

    return count


def parse_bst351(conn: sqlite3.Connection, path_351: Path) -> int:
    """
    BST351T:
      HPKODE 006-013
      BBETNR 022-025
    """
    cur = conn.cursor()
    batch: List[Tuple[str, str]] = []
    count = 0

    for line in iter_lines(path_351):
        if len(line) < 25:
            continue
        hpkode = norm(fw(line, 6, 13))
        bbetnr = norm(fw(line, 22, 25))
        if not hpkode or not bbetnr:
            continue
        batch.append((hpkode, bbetnr))
        count += 1

        if len(batch) >= 50000:
            cur.executemany(
                "INSERT OR IGNORE INTO g_bst351_hpk_bbetnr (hpkode, bbetnr) VALUES (?, ?)",
                batch,
            )
            conn.commit()
            batch.clear()

    if batch:
        cur.executemany(
            "INSERT OR IGNORE INTO g_bst351_hpk_bbetnr (hpkode, bbetnr) VALUES (?, ?)",
            batch,
        )
        conn.commit()

    return count


def parse_bst371(conn: sqlite3.Connection, path_371: Path) -> int:
    """
    BST371T:
      BBTCNR 006-009
      BBETNR 010-013
    """
    cur = conn.cursor()
    batch: List[Tuple[str, int]] = []
    count = 0

    for line in iter_lines(path_371):
        if len(line) < 13:
            continue
        bbtcnr = safe_int(fw(line, 6, 9))
        bbetnr = norm(fw(line, 10, 13))
        if bbtcnr is None or not bbetnr:
            continue
        batch.append((bbetnr, bbtcnr))
        count += 1

        if len(batch) >= 50000:
            cur.executemany(
                "INSERT OR IGNORE INTO g_bst371_bbetnr_category (bbetnr, bbtcnr) VALUES (?, ?)",
                batch,
            )
            conn.commit()
            batch.clear()

    if batch:
        cur.executemany(
            "INSERT OR IGNORE INTO g_bst371_bbetnr_category (bbetnr, bbtcnr) VALUES (?, ?)",
            batch,
        )
        conn.commit()

    return count


def parse_bst362(conn: sqlite3.Connection, path_362: Path) -> int:
    """
    BST362T:
      BBETNR 006-009
      BBETOM 015-055
    """
    cur = conn.cursor()
    batch: List[Tuple[str, str]] = []
    count = 0

    for line in iter_lines(path_362):
        if len(line) < 55:
            continue
        bbetnr = norm(fw(line, 6, 9))
        bbetom = fw(line, 15, 55).strip()
        if not bbetnr or not bbetom:
            continue
        batch.append((bbetnr, bbetom))
        count += 1

        if len(batch) >= 50000:
            # Als dezelfde BBETNR meerdere keren voorkomt, willen we de laatste tekst bewaren:
            cur.executemany(
                """
                INSERT INTO g_bst362_bbetnr_text (bbetnr, bbetom)
                VALUES (?, ?)
                ON CONFLICT(bbetnr) DO UPDATE SET bbetom=excluded.bbetom
                """,
                batch,
            )
            conn.commit()
            batch.clear()

    if batch:
        cur.executemany(
            """
            INSERT INTO g_bst362_bbetnr_text (bbetnr, bbetom)
            VALUES (?, ?)
            ON CONFLICT(bbetnr) DO UPDATE SET bbetom=excluded.bbetom
            """,
            batch,
        )
        conn.commit()

    return count


# -----------------------------
# Optional: quick sanity query
# -----------------------------
def demo_lookup(conn: sqlite3.Connection, rvg: str, category: int) -> None:
    """
    Snelle test-query in SQL (zelfde logica als je script).
    """
    rvg_norm = norm_intlike_strip_leading_zeros(rvg)
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT
            a.rvg_raw,
            a.hpkode,
            a.atnmnr,
            n.nmnaam,
            t.bbetom
        FROM g_bst004_articles a
        LEFT JOIN g_bst020_names n
            ON n.nmnr = a.atnmnr
        JOIN g_bst351_hpk_bbetnr hb
            ON hb.hpkode = a.hpkode
        JOIN g_bst371_bbetnr_category c
            ON c.bbetnr = hb.bbetnr AND c.bbtcnr = ?
        JOIN g_bst362_bbetnr_text t
            ON t.bbetnr = hb.bbetnr
        WHERE a.rvg_norm = ?
        """,
        (category, rvg_norm),
    ).fetchall()

    if not rows:
        print(f"[DEMO] Geen resultaten voor RVG={rvg} (norm={rvg_norm}) cat={category}")
        return

    print(f"[DEMO] Resultaten voor RVG={rvg} (norm={rvg_norm}) cat={category}:")
    seen = set()
    for rvg_raw, hpk, atnmnr, nmnaam, bbetom in rows:
        key = (bbetom,)
        if key in seen:
            continue
        seen.add(key)
        print(f"  - {nmnaam or '(geen naam)'} | {bbetom}")


# -----------------------------
# Main
# -----------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=RAW_DIR, help=f"Folder met BST files (default: {RAW_DIR})")
    ap.add_argument("--db-path", default=DB_PATH, help=f"Pad naar lookup.db (default: {DB_PATH})")
    ap.add_argument("--category", type=int, default=118, help="BBTCNR categorie (default 118)")
    ap.add_argument("--demo-rvg", default="", help="Optioneel: draai na import een demo lookup op dit RVG")
    args = ap.parse_args()

    raw_dir = Path(args.raw_dir)
    db_path = Path(args.db_path)

    if not raw_dir.exists():
        raise FileNotFoundError(f"RAW_DIR bestaat niet: {raw_dir}")
    if not db_path.exists():
        raise FileNotFoundError(
            f"lookup.db niet gevonden op: {db_path}\n"
            f"(Maak hem eerst aan met je bestaande util voor atc/icpc, of pas DB_PATH aan.)"
        )

    p004 = find_file(raw_dir, "BST004T")
    p020 = find_file(raw_dir, "BST020T")
    p351 = find_file(raw_dir, "BST351T")
    p371 = find_file(raw_dir, "BST371T")
    p362 = find_file(raw_dir, "BST362T")

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_schema(conn)

        print("Importeren G-standaard houdbaarheid lookup tabellen...")
        print(f"RAW_DIR: {raw_dir}")
        print(f"DB:      {db_path}\n")

        n004 = parse_bst004(conn, p004)
        print(f"BST004T: {n004} regels verwerkt")

        n020 = parse_bst020(conn, p020)
        print(f"BST020T: {n020} regels verwerkt")

        n351 = parse_bst351(conn, p351)
        print(f"BST351T: {n351} regels verwerkt")

        n371 = parse_bst371(conn, p371)
        print(f"BST371T: {n371} regels verwerkt")

        n362 = parse_bst362(conn, p362)
        print(f"BST362T: {n362} regels verwerkt")

        print("\nKlaar! lookup.db is aangevuld met G-standaard tabellen.")

        if args.demo_rvg:
            print()
            demo_lookup(conn, args.demo_rvg, args.category)

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
