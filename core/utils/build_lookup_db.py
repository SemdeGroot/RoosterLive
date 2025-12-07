import sqlite3
import os

# Pad configuratie
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE_DIR, 'raw_data')
DB_PATH = os.path.join(BASE_DIR, 'lookup.db')

# Bestandsnamen
ATC_FILE = os.path.join(RAW_DIR, 'BST801T')
ICPC_FILE = os.path.join(RAW_DIR, 'BST380T')

def create_db():
    # Verwijder oude DB als die bestaat voor een schone lei
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- ATC Tabel ---
    # Code is uniek. Index op description voor reverse lookup.
    cursor.execute("""
        CREATE TABLE atc (
            code TEXT PRIMARY KEY,
            description TEXT
        )
    """)
    cursor.execute("CREATE INDEX idx_atc_desc ON atc(description)")

    # --- ICPC Tabel ---
    cursor.execute("""
        CREATE TABLE icpc (
            code TEXT PRIMARY KEY,
            description TEXT
        )
    """)
    cursor.execute("CREATE INDEX idx_icpc_desc ON icpc(description)")

    return conn

def parse_atc(conn):
    if not os.path.exists(ATC_FILE):
        print(f"Let op: ATC bestand niet gevonden op {ATC_FILE}")
        return

    print("Verwerken ATC codes...")
    cursor = conn.cursor()
    batch = []
    
    # G-Standaard is vaak latin-1 of cp1252
    with open(ATC_FILE, 'r', encoding='latin-1') as f:
        for line in f:
            if len(line) < 13: continue
            
            # Spec: ATCODE 006-013 (len 8) -> Python [5:13]
            # Spec: ATOMS  014-093 (len 80) -> Python [13:93]
            code = line[5:13].strip()
            desc = line[13:93].strip()
            
            if code:
                batch.append((code, desc))

    cursor.executemany("INSERT OR IGNORE INTO atc (code, description) VALUES (?, ?)", batch)
    conn.commit()
    print(f"ATC: {len(batch)} regels toegevoegd.")

def parse_icpc(conn):
    if not os.path.exists(ICPC_FILE):
        print(f"Let op: ICPC bestand niet gevonden op {ICPC_FILE}")
        return

    print("Verwerken ICPC codes...")
    cursor = conn.cursor()
    batch = []

    with open(ICPC_FILE, 'r', encoding='latin-1') as f:
        for line in f:
            if len(line) < 21: continue

            # Spec: ICPC1   014-021 (len 8)  -> Python [13:21]
            # Spec: ICPCTXT 022-081 (len 60) -> Python [21:81]
            code = line[13:21].strip()
            desc = line[21:81].strip()

            if code:
                batch.append((code, desc))

    cursor.executemany("INSERT OR IGNORE INTO icpc (code, description) VALUES (?, ?)", batch)
    conn.commit()
    print(f"ICPC: {len(batch)} regels toegevoegd.")

if __name__ == "__main__":
    conn = create_db()
    try:
        parse_atc(conn)
        parse_icpc(conn)
        print(f"Succes! Database aangemaakt: {DB_PATH}")
    finally:
        conn.close()