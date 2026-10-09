"""fuck off friday - is it just you, or is nobody working today?"""
from __future__ import annotations

from flask import Flask, jsonify, render_template, request

import config
import database as db
import meter

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

db.init_db()


def _conn():
    return db.connect()


@app.route("/")
def index():
    return render_template("index.html", companies=config.COMPANIES, tz=config.TZ_NAME)


@app.route("/api/dashboard")
def api_dashboard():
    conn = _conn()
    try:
        return jsonify(meter.dashboard_payload(conn))
    finally:
        conn.close()


@app.route("/api/today")
def api_today():
    conn = _conn()
    try:
        return jsonify(meter.today_payload(conn))
    finally:
        conn.close()


@app.route("/api/history")
def api_history():
    days = request.args.get("days", type=int)
    conn = _conn()
    try:
        return jsonify(meter.history_payload(conn, days))
    finally:
        conn.close()


@app.route("/api/profile")
def api_profile():
    weeks = request.args.get("weeks", type=int)
    conn = _conn()
    try:
        return jsonify(meter.profile_payload(conn, weeks))
    finally:
        conn.close()


@app.route("/api/status")
def api_status():
    conn = _conn()
    try:
        return jsonify(meter.status_payload(conn))
    finally:
        conn.close()


@app.route("/api/productivity")
def api_productivity_legacy():
    """v1 endpoint: a single percent. Kept so old bookmarks keep working."""
    conn = _conn()
    try:
        t = meter.today_payload(conn)
    finally:
        conn.close()
    block = t.get(t["headline"]) if t["headline"] in ("reading", "settled") else None
    value = (block or {}).get("score")
    if value is None and block:
        value = block.get("raw_score")
    return jsonify({"value": value if value is not None else 0, "basis": t["headline"]})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
