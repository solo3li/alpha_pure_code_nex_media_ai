import os
import time
import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS

# ── Origins ──────────────────────────────────────────────────────────────────
ALLOWED_ORIGIN          = os.environ.get("ALLOWED_ORIGIN",          "https://ramiadel.cloud")
ALLOWED_REFERER_PREFIX  = os.environ.get("ALLOWED_REFERER_PREFIX",  "https://ramiadel.cloud/job-hunter")

# Portfolio uses the same root domain but a different section
PORTFOLIO_ORIGIN         = os.environ.get("PORTFOLIO_ORIGIN",        "https://ramiadel.cloud")
PORTFOLIO_REFERER_PREFIX = os.environ.get("PORTFOLIO_REFERER_PREFIX", "https://ramiadel.cloud")

app = Flask(__name__)
CORS(app, origins=[ALLOWED_ORIGIN, PORTFOLIO_ORIGIN])

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://jh_user:jh_secure_password_99@db:5432/job_hunter_stats"
)

_db_initialized = False


# ── Database helpers ──────────────────────────────────────────────────────────

def get_db_connection():
    retries = 10
    while retries > 0:
        try:
            conn = psycopg2.connect(DB_URL)
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            print(f"Postgres not ready yet. Retrying in 2 seconds... ({retries} retries left)")
            time.sleep(2)
    raise Exception("Could not connect to PostgreSQL database after multiple attempts.")


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # ── Existing: job-hunter stats table ─────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            key   VARCHAR(50) PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute("""
        INSERT INTO stats (key, value)
        VALUES ('visitors', 0)
        ON CONFLICT (key) DO NOTHING;
    """)

    # ── New: portfolio stats table ────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_stats (
            key   VARCHAR(50) PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute("""
        INSERT INTO portfolio_stats (key, value)
        VALUES ('visitors', 0)
        ON CONFLICT (key) DO NOTHING;
    """)

    conn.commit()
    cur.close()
    conn.close()


@app.before_request
def ensure_db():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True


# ── Request guards ────────────────────────────────────────────────────────────

def is_allowed_request():
    """Guard for job-hunter endpoints."""
    origin  = request.headers.get("Origin",  "")
    referer = request.headers.get("Referer", "")
    return origin.startswith(ALLOWED_ORIGIN) or referer.startswith(ALLOWED_REFERER_PREFIX)


def is_portfolio_request():
    """Guard for portfolio endpoints."""
    origin  = request.headers.get("Origin",  "")
    referer = request.headers.get("Referer", "")
    return origin.startswith(PORTFOLIO_ORIGIN) or referer.startswith(PORTFOLIO_REFERER_PREFIX)


# ── Job-hunter endpoints ──────────────────────────────────────────────────────

@app.route("/api/job-hunter/visit", methods=["GET", "POST"])
def visit():
    if not is_allowed_request():
        return jsonify({"error": "Forbidden"}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO stats (key, value)
            VALUES ('visitors', 1)
            ON CONFLICT (key)
            DO UPDATE SET value = stats.value + 1
            RETURNING value;
        """)
        new_count = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"count": new_count})
    except Exception as e:
        print(f"Error handling visit request: {e}")
        return jsonify({"error": "Database connection error"}), 500


@app.route("/api/job-hunter/count", methods=["GET"])
def get_count():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM stats WHERE key = 'visitors';")
        row = cur.fetchone()
        count = row[0] if row else 0
        cur.close()
        conn.close()
        return jsonify({"count": count})
    except Exception as e:
        print(f"Error handling count request: {e}")
        return jsonify({"error": "Database connection error"}), 500


# ── Portfolio endpoints ───────────────────────────────────────────────────────

@app.route("/api/portfolio/visit", methods=["GET", "POST"])
def portfolio_visit():
    if not is_portfolio_request():
        return jsonify({"error": "Forbidden"}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO portfolio_stats (key, value)
            VALUES ('visitors', 1)
            ON CONFLICT (key)
            DO UPDATE SET value = portfolio_stats.value + 1
            RETURNING value;
        """)
        new_count = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"count": new_count})
    except Exception as e:
        print(f"Error handling portfolio visit request: {e}")
        return jsonify({"error": "Database connection error"}), 500


@app.route("/api/portfolio/count", methods=["GET"])
def portfolio_get_count():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM portfolio_stats WHERE key = 'visitors';")
        row = cur.fetchone()
        count = row[0] if row else 0
        cur.close()
        conn.close()
        return jsonify({"count": count})
    except Exception as e:
        print(f"Error handling portfolio count request: {e}")
        return jsonify({"error": "Database connection error"}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7418))
    app.run(host="0.0.0.0", port=port)
