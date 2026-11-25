import os
import random
import secrets
import sqlite3
import sys
from pathlib import Path

from flask import Flask, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).parent
DATA = Path(os.environ.get("DATA_DIR", BASE))   # w Dockerze: /data
DATA.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA / "mikolajki.db"
USERS_FILE = DATA / "uczestnicy.txt"      # same imiona, jedno na linię
PASSWORDS_FILE = DATA / "hasla.txt"       # generowane automatycznie
SECRET_FILE = DATA / ".secret_key"
PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # bez mylących znaków: l, i, o, 0, 1

app = Flask(__name__, static_folder="static", static_url_path="")


def get_secret_key() -> str:
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32))
    return SECRET_FILE.read_text().strip()


app.secret_key = get_secret_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # SESSION_COOKIE_SECURE=True,  # odkomentuj, gdy działasz przez HTTPS
)


def db():
    conn = sqlite3.connect(DB_PATH, isolation_level=None, timeout=10)  # ręczne transakcje
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                   name TEXT PRIMARY KEY COLLATE NOCASE,
                   password_hash TEXT NOT NULL,
                   target TEXT
               )"""
        )
    finally:
        conn.close()


def read_names() -> list[str]:
    """Czyta same imiona z uczestnicy.txt (jedno na linię)."""
    if not USERS_FILE.exists():
        sys.exit(f"Brak pliku {USERS_FILE}. Wrzuć go do folderu data/.")
    names, seen = [], set()
    for line in USERS_FILE.read_text(encoding="utf-8").splitlines():
        name = line.split(":", 1)[0].strip()  # ewentualne ":coś" jest ignorowane
        if not name or name.startswith("#") or name.lower() in seen:
            continue
        seen.add(name.lower())
        names.append(name)
    return names


def ensure_passwords(names: list[str]) -> dict[str, str]:
    """Generuje hasła brakującym osobom i zapisuje je do hasla.txt."""
    saved = {}
    if PASSWORDS_FILE.exists():
        for line in PASSWORDS_FILE.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                n, p = line.split(":", 1)
                saved[n.strip().lower()] = p.strip()

    changed = not PASSWORDS_FILE.exists()
    for n in names:
        if not saved.get(n.lower()):
            saved[n.lower()] = "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(8))
            changed = True

    if changed:
        PASSWORDS_FILE.write_text(
            "\n".join(f"{n}:{saved[n.lower()]}" for n in names) + "\n", encoding="utf-8"
        )
        print(f"Hasła zapisano w {PASSWORDS_FILE.name}", flush=True)

    return {n: saved[n.lower()] for n in names}


def print_passwords(users: dict[str, str]):
    """Wypisuje listę haseł do konsoli (widoczne w docker compose logs)."""
    width = max(len(n) for n in users)
    print("\n" + "=" * 40, flush=True)
    print("HASŁA UCZESTNIKÓW", flush=True)
    print("=" * 40, flush=True)
    for name, password in users.items():
        print(f"{name:<{width}}  {password}", flush=True)
    print("=" * 40 + "\n", flush=True)


def sync_users():
    """Wczytuje uczestników z pliku do bazy."""
    users = ensure_passwords(read_names())
    if len(users) < 2:
        sys.exit("Potrzeba co najmniej 2 uczestników w pliku uczestnicy.txt")
    print_passwords(users)

    conn = db()
    try:
        existing = {r["name"]: r["target"] for r in conn.execute("SELECT name, target FROM users")}
        drawn = any(t is not None for t in existing.values())

        if drawn and {n.lower() for n in existing} != {n.lower() for n in users}:
            sys.exit(
                "Losowanie już się odbyło, a lista uczestników się zmieniła.\n"
                "Uruchom: docker compose run --rm mikolajki python app.py --reset  "
                "(kasuje wyniki losowania)"
            )

        conn.execute("BEGIN IMMEDIATE")
        file_names_lower = {n.lower() for n in users}
        for name in existing:
            if name.lower() not in file_names_lower:
                conn.execute("DELETE FROM users WHERE name = ?", (name,))
        for name, password in users.items():
            conn.execute(
                """INSERT INTO users (name, password_hash) VALUES (?, ?)
                   ON CONFLICT(name) DO UPDATE SET password_hash = excluded.password_hash""",
                (name, generate_password_hash(password)),
            )
        conn.execute("COMMIT")
    finally:
        conn.close()


def reset_draw():
    conn = db()
    try:
        conn.execute("UPDATE users SET target = NULL")
    finally:
        conn.close()
    print("Wyniki losowania wyczyszczone.", flush=True)


def make_assignment(names: list[str]) -> dict[str, str]:
    """Jeden duży cykl: nikt nie wylosuje siebie, nikt nie jest wylosowany dwa razy."""
    shuffled = names[:]
    random.SystemRandom().shuffle(shuffled)
    return {shuffled[i]: shuffled[(i + 1) % len(shuffled)] for i in range(len(shuffled))}


def current_user(conn):
    name = session.get("user")
    if not name:
        return None
    return conn.execute("SELECT name, target FROM users WHERE name = ?", (name,)).fetchone()


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    password = str(data.get("password", "")).strip()

    conn = db()
    try:
        row = conn.execute("SELECT name, password_hash FROM users WHERE name = ?", (name,)).fetchone()
    finally:
        conn.close()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify(error="Nieprawidłowe imię lub hasło."), 401

    session.clear()
    session["user"] = row["name"]
    return jsonify(name=row["name"])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    conn = db()
    try:
        user = current_user(conn)
    finally:
        conn.close()
    if not user:
        return jsonify(error="Niezalogowany."), 401
    return jsonify(name=user["name"], target=user["target"])


@app.post("/api/draw")
def draw():
    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE")  # blokada: tylko jedno losowanie naraz
        user = current_user(conn)
        if not user:
            conn.execute("ROLLBACK")
            return jsonify(error="Niezalogowany."), 401

        rows = conn.execute("SELECT name, target FROM users").fetchall()
        if any(r["target"] is None for r in rows):
            assignment = make_assignment([r["name"] for r in rows])
            for giver, receiver in assignment.items():
                conn.execute("UPDATE users SET target = ? WHERE name = ?", (receiver, giver))

        target = conn.execute("SELECT target FROM users WHERE name = ?", (user["name"],)).fetchone()["target"]
        conn.execute("COMMIT")
        return jsonify(target=target)
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    if "--reset" in sys.argv:
        reset_draw()
        sys.exit(0)
    sync_users()
    if "--prepare" in sys.argv:   # używane w Dockerze przed startem gunicorna
        sys.exit(0)
    app.run(host="0.0.0.0", port=5000)