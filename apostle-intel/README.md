# Apostle — Automotive Aftermarket Intel System

Crawls news signals weekly for 25 target companies. Updates the live Netlify dashboard automatically every Monday morning.

---

## How It Works

1. GitHub Actions triggers every Monday at 7am CT
2. `scripts/crawl.py` fetches recent news for each company via NewsAPI
3. Articles are scored against signal keywords (CMO hires, rebrands, acquisitions, etc.)
4. Company data is updated with new signals and intel items
5. A new HTML dashboard is built and deployed to Netlify
6. Updated `companies.json` is committed back to the repo

---

## One-Time Setup (20 minutes)

### Step 1 — Get a NewsAPI key (free)
1. Go to https://newsapi.org and create a free account
2. Copy your API key from the dashboard
3. Free tier: 100 requests/day. Our crawler uses ~50/week. You're fine.

### Step 2 — Get your Netlify credentials
1. Log into Netlify → User Settings → Applications → Personal access tokens
2. Create a new token. Copy it. This is your `NETLIFY_AUTH_TOKEN`.
3. Go to your site dashboard → Site settings → General
4. Copy the **Site ID** near the top. This is your `NETLIFY_SITE_ID`.

### Step 3 — Create a GitHub repo
1. Go to github.com → New repository
2. Name it `apostle-intel` (or anything you like)
3. Set it to Private
4. Push all these files to it:
   ```
   git init
   git add .
   git commit -m "Initial build"
   git remote add origin https://github.com/YOUR_USERNAME/apostle-intel.git
   git push -u origin main
   ```

### Step 4 — Add secrets to GitHub
1. In your repo → Settings → Secrets and variables → Actions
2. Add three secrets (New repository secret):

   | Name | Value |
   |------|-------|
   | `NEWS_API_KEY` | Your NewsAPI key |
   | `NETLIFY_SITE_ID` | Your Netlify site ID |
   | `NETLIFY_AUTH_TOKEN` | Your Netlify personal access token |

### Step 5 — Connect Netlify to deploy from GitHub (optional but cleaner)
Alternatively, you can let the script handle Netlify deploys via API (already built in).
The script will push the updated `index.html` to Netlify directly.

### Step 6 — Test it manually
1. Go to your repo → Actions tab
2. Click "Weekly Intel Crawl" → "Run workflow"
3. Watch it run. Check your Netlify URL when done.

---

## Adding or Editing Companies

Edit `data/companies.json` directly. Each company needs:

```json
{
  "id": 26,
  "name": "Company Name",
  "sub": "Description",
  "hq": "City, ST",
  "role": "mfg",        // mfg | dist | inst | plat
  "tier": 1,            // 1 = no friction, 2 = some, 3 = hard
  "priority": "high",   // high | med | low
  "signal": "warm",     // hot | warm | cold
  "trigger": "Why now note",
  "why": "Strategic rationale",
  "contact": "Who to reach",
  "outreach": "Opening angle",
  "confidence": "high", // high | mod | low
  "search_terms": ["Term 1", "Term 2"],
  "last_updated": "2026-05-06",
  "recent_intel": []
}
```

Commit the change. The next weekly run will pick it up automatically.

---

## Costs

| Service | Cost |
|---------|------|
| NewsAPI (free tier) | $0/month |
| GitHub Actions | $0/month (free tier is plenty) |
| Netlify (free tier) | $0/month |
| **Total** | **$0/month** |

If you eventually want more than 100 NewsAPI requests/day (you won't need this for a while), the Developer plan is $449/year. Not necessary yet.

---

## Files

```
apostle-intel/
├── .github/
│   └── workflows/
│       └── weekly-crawl.yml   ← GitHub Actions schedule
├── data/
│   └── companies.json         ← Source of truth, updated weekly
├── scripts/
│   └── crawl.py               ← The intelligence engine
├── index.html                 ← Built automatically, deployed to Netlify
└── README.md
```
