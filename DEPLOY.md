# Putting Stockscribes online permanently

The goal: a fixed web address that works whether or not your laptop is on, so you can put
it on your portfolio and an employer can click it any time.

Everything in the project is already set up for this. What's left needs your own accounts,
so the steps below are yours to click through — it takes about 30 minutes the first time.

---

## Which host, and what it costs

I checked the current options (August 2026). Railway and Fly.io have both ended their free
tiers; **Render still has a real one**, and it runs plain Python with no extra setup.

| | Render **Free** | Render **Starter** (~$7/month) |
|---|---|---|
| Cost | £0 | roughly £5–6/month |
| Always awake | ✗ sleeps after 15 min idle, ~1 min to wake | ✓ instant |
| Keeps your data | ✗ resets when it sleeps or redeploys | ✓ with a persistent disk |
| Own web address | ✓ | ✓ |
| Secure (https) | ✓ | ✓ |

**Start on Free.** For a portfolio it's genuinely fine — and the reset is a feature, since
every visitor gets a clean demo with the sample data. The only cost is that the first visitor
after a quiet spell waits about a minute for it to wake up, seeing a loading page.

**Move to Starter when the pharmacy starts using it for real**, because then the data has to
survive restarts. That's the moment to also switch from the single database file to Postgres.

---

## Step 1 — GitHub first (it's a prerequisite)

Render builds your site from a code repository, so GitHub has to come before deployment.

1. Create a free account at github.com if you don't have one.
2. Click **New repository**, name it `stockscribes`, keep it **Public** (employers need to
   see it), and create it.
3. On the new repository page choose **uploading an existing file**, then drag in:

   `server.py` · `index.html` · `set_password.py` · `render.yaml` · `requirements.txt` ·
   `README.md` · `DEPLOY.md` · `.gitignore`

   **Do not upload `stockscribes.db`** — that's your data, and `.gitignore` already tells
   Git to skip it.
4. Click **Commit changes**.

---

## Step 2 — Deploy on Render

1. Go to render.com and sign up **with your GitHub account** — that way it can see your code.
2. Click **New +** → **Web Service**.
3. Choose your `stockscribes` repository.
4. Render reads `render.yaml` and fills everything in for you. Check that it shows:
   - Runtime: **Python**
   - Build command: `pip install -r requirements.txt`
   - Start command: `python server.py`
   - Instance type: **Free**
5. Click **Create Web Service** and wait a few minutes.

You get an address like `https://stockscribes.onrender.com`. That's your permanent link.

---

## Step 3 — Set the demo passwords

The published sign-in details are on the login page on purpose, so anyone can try it. Because
the free plan resets the database regularly, the passwords reset with it — which is exactly
what you want for a demo, and why nothing private should ever be entered there.

**Never put real supplier prices or real staff details on the free demo.** When the pharmacy
goes live, that's a separate paid service with real passwords set through `set_password.py`.

---

## Step 4 — Your own web address (optional)

If you buy a domain (for example `stockscribes.ng` from a registrar such as Namecheap or a
Nigerian registrar), Render can use it on the free plan:

1. In your service, go to **Settings → Custom Domains → Add Custom Domain**.
2. Render shows you a DNS record to add.
3. Add it at your registrar. It usually works within an hour, https included and free.

---

## When the pharmacy goes live for real

A short checklist for that day:

- Upgrade the service to **Starter** and attach a **persistent disk**, or create a
  **Render Postgres** database and move the data there.
- Run `set_password.py` and set strong, private passwords for every real account.
- Set `DEMO_MODE=0` so the demo notice disappears.
- Remove the sample sign-in details from the login page.
- Back up the database regularly.

---

*Prices and free-tier terms were checked in August 2026 and do change — worth a quick look at
render.com/pricing before you commit.*
