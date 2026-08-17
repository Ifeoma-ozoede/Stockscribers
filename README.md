# Stockscribes — how to run it

A private website where pharmacy staff order stock from their suppliers, and suppliers keep their
prices, stock and expiry dates up to date. Built for Stockscribes Pharmacy, Lagos.

This is the **working prototype**: real logins, a real database, and data that stays saved.
It runs on your own computer for now. Putting it online comes later.

---

## Running it (2 steps)

1. Open **Terminal** (press `Cmd + Space`, type "Terminal", press Enter).
2. Type `cd ` (with the space), drag the `stockscribes` folder onto the Terminal window, press Enter.
   Then type:

   ```
   python3 server.py
   ```

3. Open your browser and go to: **http://localhost:8000**

To stop it, click on the Terminal window and press `Ctrl + C`.

> If Terminal says `python3: command not found`, install Python from python.org (free), then try again.

---

## Signing in

| Who | Email | Password |
|---|---|---|
| Pharmacy staff | `staff@stockscribes.ng` | `stockscribes123` |
| Supplier — Alpha Pharma | `alpha@supplier.ng` | `alpha123` |
| Supplier — BlueRiver | `blue@supplier.ng` | `blue123` |
| Supplier — Kola Health | `kola@supplier.ng` | `kola123` |

Open two browser windows (one normal, one private/incognito) to be signed in as the pharmacy
and a supplier at the same time — that's the best way to see updates flow between them.

**These are test passwords.** Real staff and supplier accounts get proper passwords before
this ever goes online.

---

## What to try

**As pharmacy staff**

- Search `paracetamol` — three suppliers, cheapest marked "best". Notice the cheapest one is
  short-dated (expires sooner), exactly as in real life.
- Add a few things to the basket, choose a payment method, place the order. Orders are split
  automatically so each supplier gets their own.
- Out-of-stock items can't be added — but the other suppliers for that product still show.

**As a supplier (Alpha)**

- Change a price or tap the stock label. Refresh the pharmacy window — the change is already there.
- **Add a product** — one line form.
- **Update many at once** — paste rows like:

  ```
  Emzor Paracetamol 500mg (96 tabs), 1100, 2028-03, yes
  Zinc Syrup 100ml, 1850, 2027-04, yes
  ```

  Existing products get updated, new ones added. This is the "upload your price list" idea,
  working today in its simplest form.
- **Incoming orders** — confirm an order, then mark it delivered.

**Day and night**

The site uses the light design from 6am and the dark design from 6pm, switching by itself.
The button in the top bar previews the other mode.

---

## Showing it to someone far away (a temporary web link)

This gives you a real link like `https://funny-words-here.trycloudflare.com` that your sister —
or anyone — can open from their own computer. It's free, needs no account, and the link
disappears when you close it.

**Do this first: change the passwords.** Anyone with the link can try the sample logins.

```
python3 set_password.py
```

It lists everyone who can sign in, you pick a number, and type a new password twice.
Repeat for each account you'll hand out.

**Then set up the link:**

1. Install the tool. If you have Homebrew: `brew install cloudflared`.
   Otherwise download the macOS installer from
   https://github.com/cloudflare/cloudflared/releases (pick the `.pkg` file for Apple silicon
   or Intel, whichever your Mac is) and double-click it.

2. Keep Stockscribes running in your first Terminal window (`python3 server.py`).

3. Open a **second** Terminal window (`Cmd + N`) and run:

   ```
   cloudflared tunnel --url http://localhost:8000
   ```

4. It prints a link ending in `.trycloudflare.com`. Send that to whoever you want.
   They open it in any browser and sign in.

**While the demo is on:** your Mac must stay awake with both Terminal windows running.
Closing either one ends the link. Next time you run it you get a different link — that's normal.

---

## The files

| File | What it is |
|---|---|
| `server.py` | The engine: database, logins, and all the rules. Plain Python, nothing to install. |
| `index.html` | Everything you see: the screens, styling and behaviour. |
| `stockscribes.db` | The database file — every product, price and order lives here. |
| `set_password.py` | Change anyone's password. Run before sharing the site. |
| `README.md` | This guide. |

Deleting `stockscribes.db` resets everything back to the sample data.

**Back up `stockscribes.db`** once you start entering real products — that file *is* your data.

---

## Notes for later

- **Payment methods**: the site records "Pay in advance", "Pay on account (credit)" or
  "Pay on delivery" on each order. The default is set near the top of `server.py`
  (`DEFAULT_PAYMENT`) and takes one word to change.
- **Short-dated** currently means expiring within 6 months — also a one-line change
  (`is_short_dated` in `server.py`).
- **Going online** means moving this to a rented server with a proper web address, switching
  the database to PostgreSQL, and adding HTTPS. Everything built here carries over.
