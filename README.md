# Stockscribes

**A stock-ordering platform for pharmacies and the wholesalers who supply them.**

🔗 **[Try the live demo →](https://stockscribers.onrender.com)**
Sign in as the pharmacy (`staff@stockscribes.ng` / `stockscribes123`) or as a supplier
(`alpha@supplier.ng` / `alpha123`). Sample data only.

> The demo runs on a free host, so it sleeps when idle — the first visit after a quiet spell
> takes about a minute to wake up.

---

## The problem

Pharmacies in Nigeria order stock by phone. Every restock means calling each supplier in turn to
ask what's in stock and what it costs. There's no way to compare prices across suppliers, no
record of what was agreed, and no visibility of expiry dates until the delivery arrives — which
matters, because short-dated stock sells cheaper.

## The solution

One shared catalogue with two sides to it.

**Pharmacy staff** search by product or generic name, see every supplier's price, expiry date and
stock status side by side, and order in a few clicks. Orders split automatically so each supplier
receives only their own.

**Suppliers** sign in to a simple product list where they keep their prices, stock and expiry
dates current, and confirm incoming orders. The moment they save, the pharmacy sees it.

That last part is the point: the pharmacy stops phoning around, and the supplier stops answering
the same questions all day.

---

## Features

- **Price comparison** across suppliers, with the cheapest in-stock offer marked
- **Expiry tracking** — short-dated batches flagged, since they're priced differently
- **Out-of-stock handling** that still shows the alternatives from other suppliers
- **Basket and ordering**, split per supplier, with the payment method recorded on each order
- **Supplier product management** — edit price, stock and expiry inline, saved as you type
- **Bulk price-list import** — paste rows from an existing price list to update hundreds at once
- **Order lifecycle** — sent → confirmed → delivered, visible to both sides
- **Two roles with separate permissions** — suppliers only ever see their own products and orders
- **Automatic day/night theme** — light from 6am, dark from 6pm, with a manual override
- **Works on phones**, since staff aren't always at a desk

## Built with

| | |
|---|---|
| Backend | Python 3 — standard library only, no frameworks |
| Database | SQLite |
| Frontend | Vanilla JavaScript, HTML, CSS |
| Hosting | Render |

**No dependencies.** The whole thing runs on a fresh Python install with nothing to `pip install`,
which keeps deployment simple and the code readable end to end.

**Security:** passwords hashed with PBKDF2-SHA256 and per-user salts, session tokens issued on
sign-in, and every endpoint checked for role before it does anything. A supplier can't read or
touch another supplier's data, and nothing loads at all without signing in.

---

## Running it yourself

No installation needed beyond Python 3.

```bash
python3 server.py
```

Then open **http://localhost:8000**. A database file is created next to the script and filled
with sample data on first run. Delete `stockscribes.db` to start over. Press `Ctrl + C` to stop.

To change a password: `python3 set_password.py`

## Project structure

| File | Purpose |
|---|---|
| `server.py` | Database schema, sign-in, permissions, and the whole API |
| `index.html` | Every screen — markup, styling and behaviour in one file |
| `set_password.py` | Command-line tool for changing passwords |
| `render.yaml` | Deployment configuration |
| `DEPLOY.md` | How to host it publicly, and what changes for real-world use |

---

## Status and what's next

Working prototype, deployed and usable. Built for a community pharmacy in Lagos to replace
phone-call ordering, with the wholesalers they already buy from.

Planned next:

- Move to PostgreSQL and a persistent host for real day-to-day use
- Spreadsheet upload for suppliers, alongside the existing paste-in import
- Reorder suggestions based on order history
- Cross-check product names against the NAFDAC drug registry

---

Designed and built by **Ify Ozoede** — [ifeomaozoede.com](https://ifeomaozoede.com)
