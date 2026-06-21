"""
src/data/database.py
====================
SQLite caching and storage layer for the AI Investment Advisor.

Stores analysis results so users can review past analyses and the app
can serve cached results when APIs are slow or rate-limited.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional


def _get_connection(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """Create tables if they don't exist."""
    conn = _get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS analyses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            price       REAL,
            recommendation TEXT,
            confidence  INTEGER,
            technical_json TEXT,
            sentiment_json TEXT,
            rationale   TEXT,
            engine      TEXT
        );

        CREATE TABLE IF NOT EXISTS quote_cache (
            ticker      TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            data_json   TEXT NOT NULL,
            PRIMARY KEY (ticker)
        );

        CREATE INDEX IF NOT EXISTS idx_analyses_ticker ON analyses(ticker);
        CREATE INDEX IF NOT EXISTS idx_analyses_timestamp ON analyses(timestamp);
    """)
    conn.commit()
    conn.close()


def save_analysis(
    db_path: str,
    ticker: str,
    price: float,
    recommendation: str,
    confidence: int,
    technical: dict,
    sentiment: dict,
    rationale: str,
    engine: str,
) -> int:
    """Save an analysis result and return its row ID."""
    conn = _get_connection(db_path)
    cursor = conn.execute(
        """INSERT INTO analyses
           (ticker, timestamp, price, recommendation, confidence,
            technical_json, sentiment_json, rationale, engine)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            ticker,
            datetime.utcnow().isoformat(),
            price,
            recommendation,
            confidence,
            json.dumps(technical),
            json.dumps(sentiment),
            rationale,
            engine,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_history_for_ticker(db_path: str, ticker: str, limit: int = 20) -> list[dict]:
    """Return the most recent analyses for a ticker."""
    conn = _get_connection(db_path)
    rows = conn.execute(
        """SELECT * FROM analyses
           WHERE ticker = ?
           ORDER BY timestamp DESC
           LIMIT ?""",
        (ticker.upper(), limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cache_quote(db_path: str, ticker: str, data: dict) -> None:
    """Cache quote data for a ticker."""
    conn = _get_connection(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO quote_cache (ticker, timestamp, data_json)
           VALUES (?, ?, ?)""",
        (ticker.upper(), datetime.utcnow().isoformat(), json.dumps(data)),
    )
    conn.commit()
    conn.close()


def get_cached_quote(db_path: str, ticker: str, max_age_seconds: int = 300) -> Optional[dict]:
    """Return cached quote data if fresh enough, else None."""
    conn = _get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM quote_cache WHERE ticker = ?",
        (ticker.upper(),),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    cached_time = datetime.fromisoformat(row["timestamp"])
    age = (datetime.utcnow() - cached_time).total_seconds()
    if age > max_age_seconds:
        return None

    return json.loads(row["data_json"])
