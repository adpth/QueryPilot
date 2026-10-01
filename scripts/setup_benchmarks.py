"""Sets up benchmark databases for QueryPilot evaluation.

Creates benchmarks/databases/chinook.sqlite with the schema and test data
required by the sample and golden evaluation datasets.
"""

import sqlite3
import urllib.request
from pathlib import Path

DB_DIR = Path("./benchmarks/databases")
CHINOOK_PATH = DB_DIR / "chinook.sqlite"
CHINOOK_URL = "https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sql"


def populate_offline_chinook(conn: sqlite3.Connection) -> None:
    """Populates standard Chinook tables and data when offline."""
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS genres (
        GenreId INTEGER PRIMARY KEY,
        Name TEXT
    );

    CREATE TABLE IF NOT EXISTS artists (
        ArtistId INTEGER PRIMARY KEY,
        Name TEXT
    );

    CREATE TABLE IF NOT EXISTS albums (
        AlbumId INTEGER PRIMARY KEY,
        Title TEXT,
        ArtistId INTEGER,
        FOREIGN KEY (ArtistId) REFERENCES artists (ArtistId)
    );

    CREATE TABLE IF NOT EXISTS media_types (
        MediaTypeId INTEGER PRIMARY KEY,
        Name TEXT
    );

    CREATE TABLE IF NOT EXISTS tracks (
        TrackId INTEGER PRIMARY KEY,
        Name TEXT,
        AlbumId INTEGER,
        MediaTypeId INTEGER,
        GenreId INTEGER,
        Composer TEXT,
        Milliseconds INTEGER,
        Bytes INTEGER,
        UnitPrice NUMERIC,
        FOREIGN KEY (AlbumId) REFERENCES albums (AlbumId),
        FOREIGN KEY (GenreId) REFERENCES genres (GenreId),
        FOREIGN KEY (MediaTypeId) REFERENCES media_types (MediaTypeId)
    );

    CREATE TABLE IF NOT EXISTS customers (
        CustomerId INTEGER PRIMARY KEY,
        FirstName TEXT,
        LastName TEXT,
        Company TEXT,
        Address TEXT,
        City TEXT,
        State TEXT,
        Country TEXT,
        PostalCode TEXT,
        Phone TEXT,
        Fax TEXT,
        Email TEXT,
        SupportRepId INTEGER
    );

    CREATE TABLE IF NOT EXISTS invoices (
        InvoiceId INTEGER PRIMARY KEY,
        CustomerId INTEGER,
        InvoiceDate DATETIME,
        BillingAddress TEXT,
        BillingCity TEXT,
        BillingState TEXT,
        BillingCountry TEXT,
        BillingPostalCode TEXT,
        Total NUMERIC,
        FOREIGN KEY (CustomerId) REFERENCES customers (CustomerId)
    );

    CREATE TABLE IF NOT EXISTS invoice_items (
        InvoiceLineId INTEGER PRIMARY KEY,
        InvoiceId INTEGER,
        TrackId INTEGER,
        UnitPrice NUMERIC,
        Quantity INTEGER,
        FOREIGN KEY (InvoiceId) REFERENCES invoices (InvoiceId),
        FOREIGN KEY (TrackId) REFERENCES tracks (TrackId)
    );
    """)

    # Populate Genres
    genres = [
        (1, "Rock"),
        (2, "Jazz"),
        (3, "Metal"),
        (4, "Alternative & Punk"),
        (5, "Blues"),
        (6, "Latin"),
        (7, "Reggae"),
        (8, "Pop"),
        (9, "Classical"),
    ]
    cursor.executemany("INSERT OR IGNORE INTO genres VALUES (?, ?)", genres)

    # Populate Artists
    artists = [
        (1, "AC/DC"),
        (2, "Accept"),
        (3, "Aerosmith"),
        (4, "Miles Davis"),
        (5, "Iron Maiden"),
        (6, "Metallica"),
        (7, "Queen"),
        (8, "U2"),
    ]
    cursor.executemany("INSERT OR IGNORE INTO artists VALUES (?, ?)", artists)

    # Populate Albums
    albums = [
        (1, "For Those About To Rock We Salute You", 1),
        (2, "Balls to the Wall", 2),
        (3, "Restless and Wild", 2),
        (4, "Kind of Blue", 4),
        (5, "The Number of the Beast", 5),
        (6, "Master of Puppets", 6),
        (7, "A Night at the Opera", 7),
        (8, "The Joshua Tree", 8),
    ]
    cursor.executemany("INSERT OR IGNORE INTO albums VALUES (?, ?, ?)", albums)

    # Populate Media Types
    media_types = [
        (1, "MPEG audio file"),
        (2, "Protected AAC audio file"),
        (3, "Protected MPEG-4 video file"),
        (4, "Purchased AAC audio file"),
        (5, "AAC audio file"),
    ]
    cursor.executemany("INSERT OR IGNORE INTO media_types VALUES (?, ?)", media_types)

    # Populate Tracks (with various lengths and genres)
    # Milliseconds > 300000 means longer than 5 minutes
    tracks = [
        # (TrackId, Name, AlbumId, MediaTypeId, GenreId, Composer, Milliseconds, Bytes, UnitPrice)
        (1, "For Those About To Rock", 1, 1, 1, "Angus Young", 343719, 11170334, 0.99), # > 300000, Rock
        (2, "Put The Finger On You", 1, 1, 1, "Angus Young", 205662, 6713451, 0.99),
        (3, "Let's Get It Up", 1, 1, 1, "Angus Young", 233926, 7636944, 0.99),
        (4, "Inject The Venom", 1, 1, 1, "Angus Young", 210834, 6852860, 0.99),
        (5, "Snowballed", 1, 1, 1, "Angus Young", 203102, 6599424, 0.99),
        (6, "Balls to the Wall", 2, 1, 3, "U. Dirkschneider", 342562, 11049448, 0.99), # > 300000, Metal
        (7, "Fast as a Shark", 3, 1, 3, "F. Baltes", 229381, 7475376, 0.99),
        (8, "Restless and Wild", 3, 1, 3, "F. Baltes", 252395, 8219990, 0.99),
        (9, "Princess of the Dawn", 3, 1, 3, "Deaffy", 375418, 12224759, 0.99), # > 300000, Metal
        (10, "So What", 4, 1, 2, "Miles Davis", 562133, 18274640, 0.99), # > 300000, Jazz
        (11, "Freddie Freeloader", 4, 1, 2, "Miles Davis", 589000, 19143640, 0.99), # > 300000, Jazz
        (12, "Blue in Green", 4, 1, 2, "Miles Davis", 337000, 10952000, 0.99), # > 300000, Jazz
        (13, "Invaders", 5, 1, 3, "Steve Harris", 205000, 6650000, 0.99), # Metal
        (14, "Children of the Damned", 5, 1, 3, "Steve Harris", 275000, 8950000, 0.99), # Metal
        (15, "The Prisoner", 5, 1, 3, "Steve Harris", 364000, 11850000, 0.99), # > 300000, Metal
        (16, "22 Acacia Avenue", 5, 1, 3, "Steve Harris", 397000, 12900000, 0.99), # > 300000, Metal
        (17, "The Number of the Beast", 5, 1, 3, "Steve Harris", 290000, 9450000, 0.99), # Metal
        (18, "Run to the Hills", 5, 1, 3, "Steve Harris", 233000, 7580000, 0.99), # Metal
        (19, "Hallowed Be Thy Name", 5, 1, 3, "Steve Harris", 432000, 14050000, 0.99), # > 300000, Metal
        (20, "Battery", 6, 1, 3, "James Hetfield", 312000, 10150000, 0.99), # > 300000, Metal
        (21, "Master of Puppets", 6, 1, 3, "James Hetfield", 515000, 16750000, 0.99), # > 300000, Metal
        (22, "Bohemian Rhapsody", 7, 1, 1, "Freddie Mercury", 354000, 11500000, 0.99), # > 300000, Rock
        (23, "You're My Best Friend", 7, 1, 1, "John Deacon", 172000, 5600000, 0.99), # Rock
        (24, "Where the Streets Have No Name", 8, 1, 1, "U2", 337000, 10980000, 0.99), # > 300000, Rock
        (25, "I Still Haven't Found What I'm Looking For", 8, 1, 1, "U2", 277000, 9020000, 0.99), # Rock
        (26, "With or Without You", 8, 1, 1, "U2", 296000, 9630000, 0.99), # Rock
        (27, "God Part II", 8, 1, 4, "U2", 195000, 6350000, 0.99), # Alt & Punk
        (28, "All Along the Watchtower", 8, 1, 4, "Bob Dylan", 264000, 8600000, 0.99), # Alt & Punk
        (29, "Sweetest Thing", 8, 1, 8, "U2", 183000, 5960000, 0.99), # Pop
        (30, "One", 8, 1, 1, "U2", 276000, 8980000, 0.99), # Rock
    ]
    cursor.executemany("INSERT OR IGNORE INTO tracks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tracks)

    # Populate Customers (including German customers for sample queries)
    customers = [
        (1, "Luís", "Gonçalves", "Embraer", "Av. Brigadeiro Faria Lima, 2170", "São José dos Campos", "SP", "Brazil", "12227-000", "+55 (12) 3923-5555", None, "luisg@embraer.com.br", 3),
        (2, "Leonie", "Köhler", None, "Theodor-Heuss-Straße 34", "Stuttgart", None, "Germany", "70174", "+49 0711 2842222", None, "leonekohler@surfeu.de", 5),
        (3, "François", "Tremblay", None, "1498 rue Bélanger", "Montréal", "QC", "Canada", "H2G 1A7", "+1 (514) 721-4711", None, "ftremblay@gmail.com", 3),
        (4, "Bjørn", "Hansen", None, "Ullevålsveien 14", "Oslo", None, "Norway", "0171", "+47 22 44 22 22", None, "bjorn.hansen@yahoo.no", 4),
        (5, "Hannah", "Schneider", None, "Rotebühlstraße 47", "Stuttgart", None, "Germany", "70178", "+49 0711 2842221", None, "hannah.schneider@yahoo.de", 5),
    ]
    cursor.executemany("INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", customers)

    # Populate Invoices
    invoices = [
        (1, 2, "2024-01-01 00:00:00", "Theodor-Heuss-Straße 34", "Stuttgart", None, "Germany", "70174", 23.86),
        (2, 5, "2024-01-15 00:00:00", "Rotebühlstraße 47", "Stuttgart", None, "Germany", "70178", 13.86),
        (3, 1, "2024-02-01 00:00:00", "Av. Brigadeiro Faria Lima, 2170", "São José dos Campos", "SP", "Brazil", "12227-000", 9.90),
        (4, 3, "2024-02-15 00:00:00", "1498 rue Bélanger", "Montréal", "QC", "Canada", "H2G 1A7", 15.84),
        (5, 4, "2024-03-01 00:00:00", "Ullevålsveien 14", "Oslo", None, "Norway", "0171", 3.96),
        (6, 2, "2024-03-15 00:00:00", "Theodor-Heuss-Straße 34", "Stuttgart", None, "Germany", "70174", 17.91),
    ]
    cursor.executemany("INSERT OR IGNORE INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", invoices)

    conn.commit()


def setup_benchmarks():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if CHINOOK_PATH.exists():
        print(f"Benchmark database already present at {CHINOOK_PATH}")
        return

    print(f"Setting up benchmark database at {CHINOOK_PATH}...")
    try:
        req = urllib.request.Request(CHINOOK_URL, headers={"User-Agent": "QueryPilot"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            sql_script = resp.read().decode("utf-8")
        conn = sqlite3.connect(CHINOOK_PATH)
        conn.executescript(sql_script)
        conn.close()
        print("Successfully downloaded and initialized full Chinook database.")
    except Exception as exc:
        print(f"Online download not available ({exc}); building offline Chinook database...")
        conn = sqlite3.connect(CHINOOK_PATH)
        populate_offline_chinook(conn)
        conn.close()
        print("Successfully created offline Chinook database.")


if __name__ == "__main__":
    setup_benchmarks()
