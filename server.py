#!/usr/bin/env python3
"""
Stockscribes — pharmacy stock ordering website.
Backend server + database. Uses only Python's built-in libraries (nothing to install).

Run it:      python3 server.py
Then open:   http://localhost:8000

The database is a single file, stockscribes.db, created next to this script.
Delete that file to start over with fresh sample data.
"""

import hashlib
import http.server
import json
import mimetypes
import os
import secrets
import socketserver
import sqlite3
import sys
import urllib.parse
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("STOCKSCRIBES_DB") or os.path.join(HERE, "stockscribes.db")
PORT = int(os.environ.get("PORT", 8000))

# Payment methods the website understands.
#   advance  = the pharmacy pays first, supplier delivers after
#   account  = supplier delivers first, the pharmacy pays later on credit terms
#   delivery = payment handed over when goods arrive
PAYMENT_METHODS = {
    "advance": "Pay in advance",
    "account": "Pay on account (credit)",
    "delivery": "Pay on delivery",
}
DEFAULT_PAYMENT = "advance"

# When DEMO_MODE is on, the sign-in page explains that this is a public demo running on
# sample data. Set DEMO_MODE=0 for the real pharmacy installation.
DEMO_MODE = os.environ.get("DEMO_MODE", "0") not in ("0", "", "false", "False")

SESSIONS = {}  # token -> user_id  (kept in memory; logging out or restarting clears it)


# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"


def check_password(password, stored):
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return secrets.compare_digest(hash_password(password, salt), stored)


SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('pharmacy', 'supplier')),
    supplier_id   INTEGER REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS products (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    generic  TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'Drug',
    UNIQUE (name)
);

-- One supplier's offer of one product: their price, expiry and stock status.
-- The same product can appear once per supplier.
CREATE TABLE IF NOT EXISTS offers (
    id          INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    price       INTEGER NOT NULL,           -- whole naira
    expiry      TEXT    NOT NULL,           -- 'YYYY-MM-DD'
    in_stock    INTEGER NOT NULL DEFAULT 1, -- 0 or 1
    updated_at  TEXT    NOT NULL,
    UNIQUE (product_id, supplier_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY,
    ref            TEXT NOT NULL UNIQUE,
    supplier_id    INTEGER NOT NULL REFERENCES suppliers(id),
    placed_by      INTEGER NOT NULL REFERENCES users(id),
    placed_at      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Sent',
    payment_method TEXT NOT NULL DEFAULT 'advance'
);

CREATE TABLE IF NOT EXISTS order_items (
    id           INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    expiry       TEXT NOT NULL,
    qty          INTEGER NOT NULL,
    unit_price   INTEGER NOT NULL
);
"""

SEED_SUPPLIERS = ["Alpha Pharma Distributors", "BlueRiver Wholesale", "Kola Health Supplies"]

SEED_USERS = [
    # email, password, display name, role, supplier name (None for pharmacy staff)
    ("staff@stockscribes.ng", "stockscribes123", "Stockscribes Pharmacy", "pharmacy", None),
    ("alpha@supplier.ng", "alpha123", "Alpha Pharma Distributors", "supplier", "Alpha Pharma Distributors"),
    ("blue@supplier.ng", "blue123", "BlueRiver Wholesale", "supplier", "BlueRiver Wholesale"),
    ("kola@supplier.ng", "kola123", "Kola Health Supplies", "supplier", "Kola Health Supplies"),
]

# product name, generic, category, [(supplier, price, expiry, in_stock)]
SEED_CATALOG = [
    ("Emzor Paracetamol 500mg (96 tabs)", "Paracetamol", "Drug", [
        ("Alpha Pharma Distributors", 1350, "2028-03-01", 1),
        ("BlueRiver Wholesale", 1280, "2028-01-01", 1),
        ("Kola Health Supplies", 950, "2026-10-01", 1)]),
    ("Fidson Amoxicillin 500mg (100 caps)", "Amoxicillin", "Drug", [
        ("Alpha Pharma Distributors", 6200, "2027-11-01", 1),
        ("BlueRiver Wholesale", 6450, "2027-09-01", 0)]),
    ("Ibuprofen 400mg (84 tabs)", "Ibuprofen", "Drug", [
        ("BlueRiver Wholesale", 2100, "2027-05-01", 1),
        ("Kola Health Supplies", 1600, "2026-11-15", 1)]),
    ("Vitamin C 1000mg (30 tabs)", "Ascorbic acid", "Drug", [
        ("Alpha Pharma Distributors", 3400, "2028-06-01", 1)]),
    ("ORS Sachets (box of 50)", "Oral rehydration salts", "Drug", [
        ("Kola Health Supplies", 4800, "2027-08-01", 1)]),
    ("Benylin Cough Syrup 100ml", "Diphenhydramine", "Drug", [
        ("BlueRiver Wholesale", 2950, "2026-12-01", 1)]),
    ("Amlodipine 10mg (30 tabs)", "Amlodipine", "Drug", [
        ("Alpha Pharma Distributors", 2400, "2028-04-01", 1),
        ("Kola Health Supplies", 2150, "2027-02-01", 1)]),
    ("Metformin 500mg (100 tabs)", "Metformin", "Drug", [
        ("BlueRiver Wholesale", 3600, "2027-12-01", 1)]),
    ("Dettol Antiseptic 500ml (x12)", "", "Personal care", [
        ("Alpha Pharma Distributors", 14500, "2029-01-01", 1)]),
    ("Always Ultra Pads (x24 packs)", "", "Personal care", [
        ("BlueRiver Wholesale", 21800, "2029-06-01", 1)]),
    ("Hand Sanitizer 250ml (x20)", "", "Personal care", [
        ("Kola Health Supplies", 9500, "2026-09-20", 1)]),
    ("Baby Wipes 80ct (x12)", "", "Personal care", [
        ("Alpha Pharma Distributors", 8200, "2028-02-01", 0)]),
]


def migrate(conn):
    """Small fixes to databases created by an earlier version."""
    # The demo pharmacy account used to carry the real pharmacy's name. Rename it so
    # nothing identifying appears in a public demo.
    old = conn.execute("SELECT id FROM users WHERE lower(email) = 'staff@evigor.ng'").fetchone()
    if old:
        conn.execute(
            "UPDATE users SET email = ?, password_hash = ?, display_name = ? WHERE id = ?",
            ("staff@stockscribes.ng", hash_password("stockscribes123"), "Stockscribes Pharmacy", old["id"]))
        conn.commit()
        print("Updated the pharmacy sign-in to staff@stockscribes.ng / stockscribes123")


def init_db():
    fresh = not os.path.exists(DB_PATH)
    conn = db()
    conn.executescript(SCHEMA)
    migrate(conn)
    if conn.execute("SELECT COUNT(*) c FROM suppliers").fetchone()["c"] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        for name in SEED_SUPPLIERS:
            conn.execute("INSERT INTO suppliers (name) VALUES (?)", (name,))
        for email, pw, display, role, sup in SEED_USERS:
            sid = None
            if sup:
                sid = conn.execute("SELECT id FROM suppliers WHERE name = ?", (sup,)).fetchone()["id"]
            conn.execute(
                "INSERT INTO users (email, password_hash, display_name, role, supplier_id) VALUES (?,?,?,?,?)",
                (email, hash_password(pw), display, role, sid))
        for pname, generic, cat, offers in SEED_CATALOG:
            cur = conn.execute("INSERT INTO products (name, generic, category) VALUES (?,?,?)",
                               (pname, generic, cat))
            pid = cur.lastrowid
            for sup, price, expiry, stock in offers:
                sid = conn.execute("SELECT id FROM suppliers WHERE name = ?", (sup,)).fetchone()["id"]
                conn.execute(
                    "INSERT INTO offers (product_id, supplier_id, price, expiry, in_stock, updated_at)"
                    " VALUES (?,?,?,?,?,?)", (pid, sid, price, expiry, stock, now))
        conn.commit()
        print("Sample data loaded into the database.")
    conn.close()
    return fresh


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def months_until(expiry):
    try:
        d = datetime.strptime(expiry, "%Y-%m-%d").date()
    except ValueError:
        return 99
    return (d - date.today()).days / 30.4


def is_short_dated(expiry):
    return months_until(expiry) <= 6


def next_ref(conn):
    row = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()
    return f"SS-{1041 + row['c'] + 1}"


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
class Api:
    """Each method returns (status_code, payload_dict)."""

    # ---------- auth ----------
    @staticmethod
    def login(user, body, conn):
        email = (body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
        if not row or not check_password(password, row["password_hash"]):
            return 401, {"error": "That email and password don't match. Please try again."}
        token = secrets.token_urlsafe(24)
        SESSIONS[token] = row["id"]
        return 200, {"token": token, "user": Api._user_json(row, conn)}

    @staticmethod
    def logout(user, body, conn):
        return 200, {"ok": True}

    @staticmethod
    def _user_json(row, conn):
        supplier = None
        if row["supplier_id"]:
            s = conn.execute("SELECT name FROM suppliers WHERE id = ?", (row["supplier_id"],)).fetchone()
            supplier = s["name"] if s else None
        return {"email": row["email"], "name": row["display_name"], "role": row["role"],
                "supplier": supplier, "supplier_id": row["supplier_id"]}

    @staticmethod
    def me(user, body, conn):
        return 200, {"user": Api._user_json(user, conn)}

    # ---------- catalog (pharmacy side) ----------
    @staticmethod
    def catalog(user, body, conn):
        q = (body.get("q") or "").strip().lower()
        cat = body.get("category") or "All"
        sql = ("SELECT p.id pid, p.name, p.generic, p.category, o.id oid, o.price, o.expiry,"
               " o.in_stock, s.name supplier, s.id sid"
               " FROM offers o JOIN products p ON p.id = o.product_id"
               " JOIN suppliers s ON s.id = o.supplier_id")
        where, args = [], []
        if cat != "All":
            where.append("p.category = ?")
            args.append(cat)
        if q:
            where.append("(lower(p.name) LIKE ? OR lower(p.generic) LIKE ?)")
            args += [f"%{q}%", f"%{q}%"]
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY p.name, o.price"

        groups = {}
        for r in conn.execute(sql, args):
            g = groups.setdefault(r["pid"], {
                "product_id": r["pid"], "name": r["name"], "generic": r["generic"],
                "category": r["category"], "offers": []})
            g["offers"].append({
                "offer_id": r["oid"], "supplier": r["supplier"], "supplier_id": r["sid"],
                "price": r["price"], "expiry": r["expiry"],
                "in_stock": bool(r["in_stock"]), "short_dated": is_short_dated(r["expiry"])})
        out = list(groups.values())
        for g in out:
            in_stock_prices = [o["price"] for o in g["offers"] if o["in_stock"]]
            best = min(in_stock_prices) if in_stock_prices else None
            for o in g["offers"]:
                o["best"] = bool(best is not None and o["in_stock"] and o["price"] == best)
        return 200, {"products": out, "categories": ["All", "Drug", "Personal care"]}

    # ---------- orders ----------
    @staticmethod
    def place_order(user, body, conn):
        if user["role"] != "pharmacy":
            return 403, {"error": "Only pharmacy staff can place orders."}
        items = body.get("items") or []
        payment = body.get("payment_method") or DEFAULT_PAYMENT
        if payment not in PAYMENT_METHODS:
            payment = DEFAULT_PAYMENT
        if not items:
            return 400, {"error": "Your basket is empty."}

        by_supplier = {}
        for it in items:
            row = conn.execute(
                "SELECT o.*, p.name pname, s.id sid FROM offers o"
                " JOIN products p ON p.id = o.product_id"
                " JOIN suppliers s ON s.id = o.supplier_id WHERE o.id = ?", (it.get("offer_id"),)).fetchone()
            if not row:
                continue
            if not row["in_stock"]:
                return 400, {"error": f"{row['pname']} is now out of stock with that supplier. "
                                      f"Please remove it or choose another supplier."}
            qty = max(1, int(it.get("qty") or 1))
            by_supplier.setdefault(row["sid"], []).append((row, qty))

        if not by_supplier:
            return 400, {"error": "Nothing in the basket could be ordered."}

        refs = []
        now = datetime.now().isoformat(timespec="seconds")
        for sid, lines in by_supplier.items():
            ref = next_ref(conn)
            cur = conn.execute(
                "INSERT INTO orders (ref, supplier_id, placed_by, placed_at, status, payment_method)"
                " VALUES (?,?,?,?,?,?)", (ref, sid, user["id"], now, "Sent", payment))
            oid = cur.lastrowid
            for row, qty in lines:
                conn.execute(
                    "INSERT INTO order_items (order_id, product_name, expiry, qty, unit_price)"
                    " VALUES (?,?,?,?,?)", (oid, row["pname"], row["expiry"], qty, row["price"]))
            refs.append(ref)
        conn.commit()
        return 200, {"ok": True, "refs": refs}

    @staticmethod
    def orders(user, body, conn):
        if user["role"] == "pharmacy":
            rows = conn.execute(
                "SELECT o.*, s.name supplier FROM orders o JOIN suppliers s ON s.id = o.supplier_id"
                " ORDER BY o.id DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT o.*, s.name supplier FROM orders o JOIN suppliers s ON s.id = o.supplier_id"
                " WHERE o.supplier_id = ? ORDER BY o.id DESC", (user["supplier_id"],)).fetchall()
        out = []
        for r in rows:
            items = [dict(i) for i in conn.execute(
                "SELECT product_name, expiry, qty, unit_price FROM order_items WHERE order_id = ?", (r["id"],))]
            out.append({
                "id": r["id"], "ref": r["ref"], "supplier": r["supplier"], "status": r["status"],
                "placed_at": r["placed_at"], "payment_method": r["payment_method"],
                "payment_label": PAYMENT_METHODS.get(r["payment_method"], r["payment_method"]),
                "items": items,
                "total": sum(i["qty"] * i["unit_price"] for i in items)})
        return 200, {"orders": out}

    @staticmethod
    def update_order(user, body, conn):
        if user["role"] != "supplier":
            return 403, {"error": "Only the supplier can update an order's status."}
        oid, status = body.get("order_id"), body.get("status")
        if status not in ("Confirmed", "Delivered"):
            return 400, {"error": "Unknown status."}
        row = conn.execute("SELECT * FROM orders WHERE id = ? AND supplier_id = ?",
                           (oid, user["supplier_id"])).fetchone()
        if not row:
            return 404, {"error": "Order not found."}
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, oid))
        conn.commit()
        return 200, {"ok": True}

    # ---------- supplier's own products ----------
    @staticmethod
    def my_products(user, body, conn):
        if user["role"] != "supplier":
            return 403, {"error": "Only suppliers have a product list."}
        rows = conn.execute(
            "SELECT o.id offer_id, o.price, o.expiry, o.in_stock, o.updated_at,"
            " p.name, p.generic, p.category FROM offers o JOIN products p ON p.id = o.product_id"
            " WHERE o.supplier_id = ? ORDER BY p.category, p.name", (user["supplier_id"],)).fetchall()
        return 200, {"products": [{
            "offer_id": r["offer_id"], "name": r["name"], "generic": r["generic"],
            "category": r["category"], "price": r["price"], "expiry": r["expiry"],
            "in_stock": bool(r["in_stock"]), "short_dated": is_short_dated(r["expiry"]),
            "updated_at": r["updated_at"]} for r in rows]}

    @staticmethod
    def update_offer(user, body, conn):
        if user["role"] != "supplier":
            return 403, {"error": "Only suppliers can update their products."}
        row = conn.execute("SELECT * FROM offers WHERE id = ? AND supplier_id = ?",
                           (body.get("offer_id"), user["supplier_id"])).fetchone()
        if not row:
            return 404, {"error": "Product not found on your list."}
        price = row["price"]
        expiry = row["expiry"]
        stock = row["in_stock"]
        if body.get("price") is not None:
            try:
                price = max(0, int(body["price"]))
            except (TypeError, ValueError):
                return 400, {"error": "Price must be a whole number in naira."}
        if body.get("expiry"):
            expiry = body["expiry"]
            if len(expiry) == 7:          # 'YYYY-MM' from a month picker
                expiry += "-01"
            try:
                datetime.strptime(expiry, "%Y-%m-%d")
            except ValueError:
                return 400, {"error": "Expiry date is not valid."}
        if body.get("in_stock") is not None:
            stock = 1 if body["in_stock"] else 0
        conn.execute("UPDATE offers SET price = ?, expiry = ?, in_stock = ?, updated_at = ? WHERE id = ?",
                     (price, expiry, stock, datetime.now().isoformat(timespec="seconds"), row["id"]))
        conn.commit()
        return 200, {"ok": True}

    @staticmethod
    def add_product(user, body, conn):
        if user["role"] != "supplier":
            return 403, {"error": "Only suppliers can add products."}
        name = (body.get("name") or "").strip()
        if not name:
            return 400, {"error": "Please give the product a name."}
        generic = (body.get("generic") or "").strip()
        category = body.get("category") or "Drug"
        expiry = body.get("expiry") or ""
        if len(expiry) == 7:
            expiry += "-01"
        try:
            datetime.strptime(expiry, "%Y-%m-%d")
        except ValueError:
            return 400, {"error": "Please give a valid expiry date."}
        try:
            price = max(0, int(body.get("price") or 0))
        except (TypeError, ValueError):
            return 400, {"error": "Price must be a whole number in naira."}

        prod = conn.execute("SELECT * FROM products WHERE lower(name) = lower(?)", (name,)).fetchone()
        if prod:
            pid = prod["id"]
            dupe = conn.execute("SELECT id FROM offers WHERE product_id = ? AND supplier_id = ?",
                                (pid, user["supplier_id"])).fetchone()
            if dupe:
                return 400, {"error": "That product is already on your list — edit it instead."}
        else:
            pid = conn.execute("INSERT INTO products (name, generic, category) VALUES (?,?,?)",
                               (name, generic, category)).lastrowid
        conn.execute("INSERT INTO offers (product_id, supplier_id, price, expiry, in_stock, updated_at)"
                     " VALUES (?,?,?,?,1,?)",
                     (pid, user["supplier_id"], price, expiry, datetime.now().isoformat(timespec="seconds")))
        conn.commit()
        return 200, {"ok": True}

    @staticmethod
    def import_price_list(user, body, conn):
        """Bulk update from pasted rows: name, price, expiry, in stock.
        This is the 'upload your price list' idea, done simply."""
        if user["role"] != "supplier":
            return 403, {"error": "Only suppliers can import a price list."}
        text = body.get("text") or ""
        updated = added = skipped = 0
        now = datetime.now().isoformat(timespec="seconds")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.replace("\t", ",").split(",")]
            if len(parts) < 3:
                skipped += 1
                continue
            name, price_s, expiry = parts[0], parts[1], parts[2]
            stock = 1
            if len(parts) >= 4:
                stock = 0 if parts[3].lower() in ("0", "no", "out", "out of stock", "false") else 1
            try:
                price = int(float(price_s.replace("₦", "").replace(",", "")))
            except ValueError:
                skipped += 1
                continue
            if len(expiry) == 7:
                expiry += "-01"
            try:
                datetime.strptime(expiry, "%Y-%m-%d")
            except ValueError:
                skipped += 1
                continue
            prod = conn.execute("SELECT * FROM products WHERE lower(name) = lower(?)", (name,)).fetchone()
            if prod:
                pid = prod["id"]
            else:
                pid = conn.execute("INSERT INTO products (name, generic, category) VALUES (?,?,?)",
                                   (name, "", "Drug")).lastrowid
            existing = conn.execute("SELECT id FROM offers WHERE product_id = ? AND supplier_id = ?",
                                    (pid, user["supplier_id"])).fetchone()
            if existing:
                conn.execute("UPDATE offers SET price=?, expiry=?, in_stock=?, updated_at=? WHERE id=?",
                             (price, expiry, stock, now, existing["id"]))
                updated += 1
            else:
                conn.execute("INSERT INTO offers (product_id, supplier_id, price, expiry, in_stock, updated_at)"
                             " VALUES (?,?,?,?,?,?)", (pid, user["supplier_id"], price, expiry, stock, now))
                added += 1
        conn.commit()
        return 200, {"ok": True, "updated": updated, "added": added, "skipped": skipped}


PUBLIC_ROUTES = {"login"}
ROUTES = {
    "login": Api.login, "logout": Api.logout, "me": Api.me,
    "catalog": Api.catalog, "place_order": Api.place_order, "orders": Api.orders,
    "update_order": Api.update_order, "my_products": Api.my_products,
    "update_offer": Api.update_offer, "add_product": Api.add_product,
    "import_price_list": Api.import_price_list,
}


# --------------------------------------------------------------------------
# web server
# --------------------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "Stockscribes"

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet

    # ---- helpers ----
    def _send(self, code, body, content_type="application/json"):
        data = json.dumps(body).encode() if content_type == "application/json" else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _current_user(self, conn):
        auth = self.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        uid = SESSIONS.get(token)
        if not uid:
            return None
        return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

    # ---- routes ----
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._serve_file("index.html", "text/html; charset=utf-8")
        if path == "/api/payment-methods":
            return self._send(200, {"methods": PAYMENT_METHODS, "default": DEFAULT_PAYMENT})
        if path == "/api/site-info":
            return self._send(200, {"demo": DEMO_MODE})
        safe = os.path.normpath(path).lstrip("/\\")
        full = os.path.join(HERE, safe)
        if os.path.isfile(full) and full.startswith(HERE):
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            return self._serve_file(safe, ctype)
        self._send(404, {"error": "Not found"})

    def _serve_file(self, relative, ctype):
        try:
            with open(os.path.join(HERE, relative), "rb") as fh:
                self._send(200, fh.read(), ctype)
        except OSError:
            self._send(404, {"error": "Not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._send(404, {"error": "Not found"})
        action = path[5:]
        handler = ROUTES.get(action)
        if not handler:
            return self._send(404, {"error": "Unknown action"})

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "Bad request"})

        conn = db()
        try:
            user = self._current_user(conn)
            if action not in PUBLIC_ROUTES and not user:
                return self._send(401, {"error": "Please sign in again."})
            if action == "logout":
                auth = self.headers.get("Authorization", "")
                SESSIONS.pop(auth[7:] if auth.startswith("Bearer ") else "", None)
            code, payload = handler(user, body, conn)
            self._send(code, payload)
        finally:
            conn.close()


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    init_db()
    port = PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    print("\n  Stockscribes is running.")
    print(f"  Open this in your browser:  http://localhost:{port}\n")
    print("  Sign in with:")
    print("    Pharmacy staff   staff@stockscribes.ng     / stockscribes123")
    print("    Supplier (Alpha) alpha@supplier.ng   / alpha123")
    print("    Supplier (Blue)  blue@supplier.ng    / blue123")
    print("    Supplier (Kola)  kola@supplier.ng    / kola123\n")
    print("  Press Ctrl+C to stop.\n")
    try:
        Server(("0.0.0.0", port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.\n")


if __name__ == "__main__":
    main()
