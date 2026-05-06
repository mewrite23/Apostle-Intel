#!/usr/bin/env python3
"""
Apostle Automotive Aftermarket Intelligence Crawler
Runs weekly via GitHub Actions. Fetches news signals for each target company,
scores relevance, updates company data, and rebuilds the HTML dashboard.
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
NETLIFY_SITE_ID = os.environ.get("NETLIFY_SITE_ID", "")
NETLIFY_AUTH_TOKEN = os.environ.get("NETLIFY_AUTH_TOKEN", "")

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "companies.json"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "index.html"

# Keywords that indicate a high-value signal for Apostle
SIGNAL_KEYWORDS_HOT = [
    "new cmo", "new chief marketing", "hired cmo", "appoints cmo",
    "rebrand", "rebranding", "brand refresh", "new brand",
    "acquisition", "acquired", "merger", "new ceo", "leadership change",
    "restructuring", "turnaround", "new campaign", "agency review",
    "marketing agency", "creative agency", "brand strategy",
]

SIGNAL_KEYWORDS_WARM = [
    "marketing", "brand", "campaign", "launch", "expansion",
    "new product", "partnership", "sponsorship", "advertising",
    "growth", "investment", "new market",
]

# ── News Fetching ───────────────────────────────────────────────────────────────

def fetch_news_for_company(company: dict) -> list[dict]:
    """Fetch recent news articles for a company using NewsAPI."""
    if not NEWS_API_KEY:
        print(f"  [skip] No NEWS_API_KEY set — using mock data for {company['name']}")
        return []

    articles = []
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    for term in company["search_terms"][:2]:  # Limit to 2 terms to stay within API quota
        try:
            params = urllib.parse.urlencode({
                "q": term,
                "from": week_ago,
                "sortBy": "relevancy",
                "language": "en",
                "pageSize": 5,
                "apiKey": NEWS_API_KEY,
            })
            url = f"https://newsapi.org/v2/everything?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "ApostleIntel/1.0"})

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                if data.get("status") == "ok":
                    for article in data.get("articles", []):
                        articles.append({
                            "title": article.get("title", ""),
                            "url": article.get("url", ""),
                            "source": article.get("source", {}).get("name", ""),
                            "published": article.get("publishedAt", "")[:10],
                            "description": article.get("description", "") or "",
                        })
            time.sleep(0.5)  # Polite delay between requests

        except Exception as e:
            print(f"  [warn] News fetch failed for '{term}': {e}")

    # Deduplicate by URL
    seen = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)

    return unique

# ── Signal Scoring ─────────────────────────────────────────────────────────────

def score_articles(articles: list[dict]) -> tuple[str, str, list[dict]]:
    """
    Score articles against signal keywords.
    Returns (signal_level, best_trigger, top_articles).
    """
    if not articles:
        return None, None, []

    scored = []
    for article in articles:
        text = f"{article['title']} {article['description']}".lower()
        hot_hits = sum(1 for kw in SIGNAL_KEYWORDS_HOT if kw in text)
        warm_hits = sum(1 for kw in SIGNAL_KEYWORDS_WARM if kw in text)
        score = hot_hits * 3 + warm_hits
        if score > 0:
            scored.append({**article, "score": score, "hot_hits": hot_hits})

    if not scored:
        return None, None, []

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:3]

    # Determine signal level from best article
    best = scored[0]
    if best["hot_hits"] >= 1:
        signal = "hot"
    elif best["score"] >= 2:
        signal = "warm"
    else:
        signal = None

    # Extract a trigger phrase from the best headline
    trigger = best["title"][:80] if best["title"] else None
    # Clean off source suffix patterns like " - Reuters"
    trigger = re.sub(r'\s*[-|]\s*\w[\w\s]*$', '', trigger).strip()

    return signal, trigger, top

# ── HTML Builder ────────────────────────────────────────────────────────────────

def build_html(companies: list[dict]) -> str:
    updated_str = datetime.now().strftime("%B %d, %Y")
    companies_json = json.dumps(companies, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Apostle — Automotive Aftermarket Target Universe</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap');
  :root {{
    --bg:#0a0a08;--surface:#111110;--border:#1e1e1c;--accent:#c8ff00;
    --text:#e8e6e0;--text-muted:#6b6960;--text-dim:#3a3933;
    --tier1:#c8ff00;--tier2:#ffa940;--tier3:#ff4d4d;
    --role-mfg:#4da6ff;--role-dist:#a78bfa;--role-inst:#34d399;--role-plat:#fb923c;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:'DM Mono',monospace;font-size:13px;min-height:100vh}}
  header{{padding:32px 40px 24px;border-bottom:1px solid var(--border);display:flex;align-items:flex-end;justify-content:space-between;gap:24px}}
  .brand{{font-family:'Syne',sans-serif;font-weight:800;font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--accent)}}
  h1{{font-family:'Syne',sans-serif;font-size:22px;font-weight:700;color:var(--text);margin-top:6px;letter-spacing:-.02em}}
  .meta{{color:var(--text-muted);font-size:11px;text-align:right;line-height:1.8}}
  .controls{{padding:20px 40px;border-bottom:1px solid var(--border);display:flex;gap:12px;flex-wrap:wrap;align-items:center}}
  .filter-group{{display:flex;gap:6px;align-items:center}}
  .filter-label{{color:var(--text-muted);font-size:10px;letter-spacing:.1em;text-transform:uppercase;margin-right:4px}}
  .pill{{background:var(--surface);border:1px solid var(--border);color:var(--text-muted);padding:5px 12px;border-radius:2px;cursor:pointer;font-family:'DM Mono',monospace;font-size:11px;transition:all .15s;white-space:nowrap}}
  .pill:hover{{border-color:var(--text-muted);color:var(--text)}}
  .pill.active{{background:var(--accent);color:#000;border-color:var(--accent);font-weight:500}}
  .search-wrap{{margin-left:auto}}
  input[type=text]{{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:6px 14px;font-family:'DM Mono',monospace;font-size:12px;width:220px;outline:none;border-radius:2px;transition:border-color .15s}}
  input[type=text]:focus{{border-color:var(--accent)}}
  input[type=text]::placeholder{{color:var(--text-dim)}}
  .sort-controls{{padding:10px 40px;border-bottom:1px solid var(--border);display:flex;gap:0}}
  .sort-btn{{background:none;border:none;color:var(--text-muted);font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.08em;text-transform:uppercase;cursor:pointer;padding:4px 16px 4px 0;transition:color .15s;display:flex;align-items:center;gap:5px}}
  .sort-btn:hover{{color:var(--text)}}
  .sort-btn.active{{color:var(--accent)}}
  .stat-bar{{padding:14px 40px;border-bottom:1px solid var(--border);display:flex;gap:32px}}
  .stat{{display:flex;flex-direction:column;gap:2px}}
  .stat-val{{font-family:'Syne',sans-serif;font-size:20px;font-weight:700;color:var(--accent)}}
  .stat-label{{font-size:10px;color:var(--text-muted);letter-spacing:.08em;text-transform:uppercase}}
  .grid-header{{display:grid;grid-template-columns:2fr 1.2fr .8fr .7fr .7fr 1fr 1fr;gap:0;padding:10px 40px;border-bottom:1px solid var(--border);color:var(--text-muted);font-size:10px;letter-spacing:.08em;text-transform:uppercase}}
  .company-list{{padding:0 40px 60px}}
  .company-row{{display:grid;grid-template-columns:2fr 1.2fr .8fr .7fr .7fr 1fr 1fr;gap:0;padding:14px 0;border-bottom:1px solid var(--border);align-items:center;cursor:pointer;transition:background .12s;margin:0 -40px;padding-left:40px;padding-right:40px}}
  .company-row:hover{{background:rgba(255,255,255,.02)}}
  .company-row.expanded{{background:rgba(200,255,0,.03)}}
  .company-name{{font-family:'Syne',sans-serif;font-weight:600;font-size:14px;color:var(--text)}}
  .company-sub{{font-size:10px;color:var(--text-muted);margin-top:2px}}
  .hq{{color:var(--text-muted);font-size:12px}}
  .role-badge{{display:inline-block;padding:2px 8px;border-radius:2px;font-size:10px;font-weight:500;letter-spacing:.05em;text-transform:uppercase}}
  .role-mfg{{background:rgba(77,166,255,.12);color:var(--role-mfg)}}
  .role-dist{{background:rgba(167,139,250,.12);color:var(--role-dist)}}
  .role-inst{{background:rgba(52,211,153,.12);color:var(--role-inst)}}
  .role-plat{{background:rgba(251,146,60,.12);color:var(--role-plat)}}
  .proximity-bar{{display:flex;align-items:center;gap:8px}}
  .prox-dots{{display:flex;gap:3px}}
  .dot{{width:7px;height:7px;border-radius:50%}}
  .dot.on-t1{{background:var(--tier1)}}
  .dot.on-t2{{background:var(--tier2)}}
  .dot.on-t3{{background:var(--tier3)}}
  .dot.off{{background:var(--border)}}
  .prox-label{{font-size:10px;color:var(--text-muted)}}
  .signal-indicator{{display:flex;align-items:center;gap:6px}}
  .signal-dot{{width:8px;height:8px;border-radius:50%}}
  .signal-hot .signal-dot{{background:var(--tier1);box-shadow:0 0 6px var(--tier1)}}
  .signal-warm .signal-dot{{background:var(--tier2)}}
  .signal-cold .signal-dot{{background:var(--text-dim);border:1px solid #333}}
  .signal-text{{font-size:11px}}
  .signal-hot .signal-text{{color:var(--tier1)}}
  .signal-warm .signal-text{{color:var(--tier2)}}
  .signal-cold .signal-text{{color:var(--text-muted)}}
  .priority-num{{font-family:'Syne',sans-serif;font-weight:700;font-size:16px}}
  .p-high{{color:var(--accent)}}
  .p-med{{color:var(--tier2)}}
  .p-low{{color:var(--text-muted)}}
  .expand-panel{{display:none;background:var(--surface);border:1px solid var(--border);padding:20px 24px;margin:0 -40px;margin-bottom:2px;padding-left:40px;padding-right:40px}}
  .expand-panel.open{{display:block}}
  .expand-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:24px}}
  .expand-section h4{{font-family:'Syne',sans-serif;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:8px}}
  .expand-section p,.expand-section li{{font-size:12px;color:var(--text-muted);line-height:1.7}}
  .intel-item{{margin-top:8px;padding:10px 12px;background:rgba(200,255,0,.03);border-left:2px solid var(--accent)}}
  .intel-title{{font-size:11px;color:var(--text);line-height:1.5}}
  .intel-meta{{font-size:10px;color:var(--text-muted);margin-top:3px}}
  .intel-link{{color:var(--accent);text-decoration:none;font-size:10px}}
  .intel-link:hover{{text-decoration:underline}}
  .new-badge{{display:inline-block;background:var(--accent);color:#000;font-size:9px;font-weight:500;padding:1px 6px;border-radius:2px;margin-left:6px;letter-spacing:.05em}}
  .confidence{{display:inline-block;font-size:9px;letter-spacing:.1em;text-transform:uppercase;padding:1px 6px;border:1px solid;border-radius:2px;margin-left:6px;vertical-align:middle}}
  .conf-high{{color:var(--accent);border-color:var(--accent)}}
  .conf-mod{{color:var(--tier2);border-color:var(--tier2)}}
  .conf-low{{color:var(--text-muted);border-color:var(--text-dim)}}
  .empty-state{{padding:60px 0;text-align:center;color:var(--text-muted)}}
  .updated-note{{padding:8px 40px;background:rgba(200,255,0,.04);border-bottom:1px solid var(--border);font-size:10px;color:var(--text-muted);letter-spacing:.05em}}
</style>
</head>
<body>

<header>
  <div>
    <div class="brand">Apostle</div>
    <h1>Automotive Aftermarket — Target Universe</h1>
  </div>
  <div class="meta">Proximity-sorted · Signal-weighted<br>Auto-updated weekly</div>
</header>

<div class="updated-note">⟳ Last crawled: {updated_str} — signals sourced from NewsAPI across {len(companies)} companies</div>

<div class="controls">
  <div class="filter-group">
    <span class="filter-label">Role</span>
    <button class="pill active" onclick="filter('role','all',this)">All</button>
    <button class="pill" onclick="filter('role','mfg',this)">Manufacturer</button>
    <button class="pill" onclick="filter('role','dist',this)">Distributor</button>
    <button class="pill" onclick="filter('role','inst',this)">Installer</button>
  </div>
  <div class="filter-group">
    <span class="filter-label">Tier</span>
    <button class="pill active" onclick="filter('tier','all',this)">All</button>
    <button class="pill" onclick="filter('tier','1',this)">Tier 1 — No friction</button>
    <button class="pill" onclick="filter('tier','2',this)">Tier 2 — Some friction</button>
    <button class="pill" onclick="filter('tier','3',this)">Tier 3 — Hard</button>
  </div>
  <div class="filter-group">
    <span class="filter-label">Signal</span>
    <button class="pill active" onclick="filter('signal','all',this)">All</button>
    <button class="pill" onclick="filter('signal','hot',this)">🟢 Hot</button>
    <button class="pill" onclick="filter('signal','warm',this)">🟡 Warm</button>
  </div>
  <div class="search-wrap">
    <input type="text" id="search" placeholder="Search companies..." oninput="renderList()">
  </div>
</div>

<div class="sort-controls">
  <button class="sort-btn active" id="sort-prox" onclick="setSort('proximity')">Proximity ↓</button>
  <button class="sort-btn" id="sort-pri" onclick="setSort('priority')">Priority ↓</button>
  <button class="sort-btn" id="sort-sig" onclick="setSort('signal')">Signal ↓</button>
  <button class="sort-btn" id="sort-name" onclick="setSort('name')">A–Z ↓</button>
</div>

<div class="stat-bar">
  <div class="stat"><div class="stat-val" id="stat-total">—</div><div class="stat-label">Companies</div></div>
  <div class="stat"><div class="stat-val" id="stat-t1">—</div><div class="stat-label">Tier 1 HQ</div></div>
  <div class="stat"><div class="stat-val" id="stat-hot">—</div><div class="stat-label">Hot Signals</div></div>
  <div class="stat"><div class="stat-val" id="stat-intel">—</div><div class="stat-label">New Intel Items</div></div>
</div>

<div class="grid-header">
  <div>Company</div><div>HQ</div><div>Role</div><div>Proximity</div>
  <div>Priority</div><div>Signal</div><div>Trigger</div>
</div>

<div class="company-list" id="company-list"></div>

<script>
const companies = {companies_json};
let activeFilters = {{role:'all',tier:'all',signal:'all'}};
let currentSort = 'proximity';
let expandedId = null;

function proximityScore(t){{return t===1?3:t===2?2:1}}
function signalScore(s){{return s==='hot'?3:s==='warm'?2:1}}
function priorityScore(p){{return p==='high'?3:p==='med'?2:1}}

function filter(type,val,btn){{
  activeFilters[type]=val;
  btn.parentElement.querySelectorAll('.pill').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  renderList();
}}

function setSort(s){{
  currentSort=s;
  document.querySelectorAll('.sort-btn').forEach(b=>b.classList.remove('active'));
  const map={{proximity:'prox',priority:'pri',signal:'sig',name:'name'}};
  document.getElementById('sort-'+map[s]).classList.add('active');
  renderList();
}}

function getFiltered(){{
  const q=document.getElementById('search').value.toLowerCase();
  return companies.filter(c=>{{
    if(activeFilters.role!=='all'&&c.role!==activeFilters.role)return false;
    if(activeFilters.tier!=='all'&&String(c.tier)!==activeFilters.tier)return false;
    if(activeFilters.signal!=='all'&&c.signal!==activeFilters.signal)return false;
    if(q&&!c.name.toLowerCase().includes(q)&&!c.hq.toLowerCase().includes(q)&&!c.sub.toLowerCase().includes(q))return false;
    return true;
  }});
}}

function getSorted(list){{
  return [...list].sort((a,b)=>{{
    if(currentSort==='proximity')return proximityScore(b.tier)-proximityScore(a.tier)||signalScore(b.signal)-signalScore(a.signal);
    if(currentSort==='priority')return priorityScore(b.priority)-priorityScore(a.priority);
    if(currentSort==='signal')return signalScore(b.signal)-signalScore(a.signal);
    return a.name.localeCompare(b.name);
  }});
}}

function roleBadge(r){{
  const m={{mfg:['role-mfg','MFG'],dist:['role-dist','DIST'],inst:['role-inst','INST'],plat:['role-plat','PLAT']}};
  const [cls,lbl]=m[r]||['','?'];
  return `<span class="role-badge ${{cls}}">${{lbl}}</span>`;
}}

function proximityDots(tier){{
  const cls=tier===1?'on-t1':tier===2?'on-t2':'on-t3';
  const dots=[1,2,3].map(i=>`<div class="dot ${{i<=(4-tier)?cls:'off'}}"></div>`).join('');
  const labels={{1:'No friction',2:'Some friction',3:'Hard'}};
  return `<div class="proximity-bar"><div class="prox-dots">${{dots}}</div><span class="prox-label">${{labels[tier]}}</span></div>`;
}}

function signalEl(signal){{
  const lbl={{hot:'Hot',warm:'Warm',cold:'Cold'}}[signal];
  return `<div class="signal-indicator signal-${{signal}}"><div class="signal-dot"></div><span class="signal-text">${{lbl}}</span></div>`;
}}

function priorityEl(p){{
  const cls={{high:'p-high',med:'p-med',low:'p-low'}}[p];
  const sym={{high:'↑',med:'→',low:'↓'}}[p];
  return `<span class="priority-num ${{cls}}">${{sym}}</span>`;
}}

function confBadge(c){{
  const cls=c==='high'?'conf-high':c==='mod'?'conf-mod':'conf-low';
  return `<span class="confidence ${{cls}}">${{c}}</span>`;
}}

function intelItems(items){{
  if(!items||!items.length)return '<p style="color:var(--text-dim);font-size:11px">No new intel this week.</p>';
  return items.map(a=>`
    <div class="intel-item">
      <div class="intel-title">${{a.title}}</div>
      <div class="intel-meta">${{a.source}} · ${{a.published}} · <a class="intel-link" href="${{a.url}}" target="_blank">Read →</a></div>
    </div>
  `).join('');
}}

function toggleExpand(id){{
  expandedId=expandedId===id?null:id;
  renderList();
}}

function renderList(){{
  const filtered=getFiltered();
  const sorted=getSorted(filtered);
  const totalIntel=filtered.reduce((sum,c)=>sum+(c.recent_intel||[]).length,0);

  document.getElementById('stat-total').textContent=filtered.length;
  document.getElementById('stat-t1').textContent=filtered.filter(c=>c.tier===1).length;
  document.getElementById('stat-hot').textContent=filtered.filter(c=>c.signal==='hot').length;
  document.getElementById('stat-intel').textContent=totalIntel;

  const container=document.getElementById('company-list');
  if(!sorted.length){{container.innerHTML='<div class="empty-state">No companies match current filters.</div>';return;}}

  container.innerHTML=sorted.map(c=>{{
    const isOpen=expandedId===c.id;
    const hasIntel=(c.recent_intel||[]).length>0;
    return `
      <div class="company-row ${{isOpen?'expanded':''}}" onclick="toggleExpand(${{c.id}})">
        <div>
          <div class="company-name">${{c.name}}${{hasIntel?'<span class="new-badge">NEW INTEL</span>':''}}</div>
          <div class="company-sub">${{c.sub}}</div>
        </div>
        <div class="hq">${{c.hq}}</div>
        <div>${{roleBadge(c.role)}}</div>
        <div>${{proximityDots(c.tier)}}</div>
        <div>${{priorityEl(c.priority)}}</div>
        <div>${{signalEl(c.signal)}}</div>
        <div style="font-size:11px;color:var(--text-muted);line-height:1.4">${{c.trigger}}</div>
      </div>
      <div class="expand-panel ${{isOpen?'open':''}}">
        <div class="expand-grid">
          <div class="expand-section">
            <h4>Why now ${{confBadge(c.confidence)}}</h4>
            <p>${{c.why}}</p>
          </div>
          <div class="expand-section">
            <h4>Who to contact</h4>
            <p>${{c.contact}}</p>
            <br>
            <h4>Outreach angle</h4>
            <p style="color:var(--text);font-style:italic">"${{c.outreach}}"</p>
          </div>
          <div class="expand-section">
            <h4>This week's intel</h4>
            ${{intelItems(c.recent_intel)}}
          </div>
        </div>
      </div>
    `;
  }}).join('');
}}

renderList();
</script>
</body>
</html>"""

# ── Netlify Deploy ──────────────────────────────────────────────────────────────

def deploy_to_netlify(html_content: str) -> bool:
    """Deploy updated HTML to Netlify via API."""
    if not NETLIFY_SITE_ID or not NETLIFY_AUTH_TOKEN:
        print("[skip] Netlify credentials not set — writing local file only.")
        return False

    try:
        import hashlib
        content_bytes = html_content.encode("utf-8")
        sha1 = hashlib.sha1(content_bytes).hexdigest()

        # Step 1: Create a deploy
        deploy_data = json.dumps({
            "files": {"index.html": sha1}
        }).encode("utf-8")

        req = urllib.request.Request(
            f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys",
            data=deploy_data,
            headers={
                "Authorization": f"Bearer {NETLIFY_AUTH_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            deploy = json.loads(resp.read().decode())
            deploy_id = deploy["id"]
            print(f"  Created deploy: {deploy_id}")

        # Step 2: Upload the file
        upload_req = urllib.request.Request(
            f"https://api.netlify.com/api/v1/deploys/{deploy_id}/files/index.html",
            data=content_bytes,
            headers={
                "Authorization": f"Bearer {NETLIFY_AUTH_TOKEN}",
                "Content-Type": "application/octet-stream",
            },
            method="PUT"
        )

        with urllib.request.urlopen(upload_req, timeout=30) as resp:
            print(f"  Upload status: {resp.status}")

        print(f"  Deployed successfully to Netlify.")
        return True

    except Exception as e:
        print(f"  [error] Netlify deploy failed: {e}")
        return False

# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"Apostle Intel Crawler — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # Load company data
    with open(DATA_FILE) as f:
        companies = json.load(f)

    print(f"Loaded {len(companies)} companies.\n")

    # Process each company
    for company in companies:
        print(f"→ {company['name']} ({company['hq']})")

        articles = fetch_news_for_company(company)
        print(f"  Found {len(articles)} articles")

        if articles:
            new_signal, new_trigger, top_articles = score_articles(articles)

            # Update signal only if we found something stronger
            if new_signal:
                signal_rank = {"hot": 3, "warm": 2, "cold": 1}
                current_rank = signal_rank.get(company["signal"], 1)
                new_rank = signal_rank.get(new_signal, 1)

                if new_rank >= current_rank:
                    print(f"  Signal: {company['signal']} → {new_signal}")
                    company["signal"] = new_signal

                if new_trigger:
                    company["trigger"] = new_trigger
                    print(f"  Trigger updated: {new_trigger[:60]}...")

            company["recent_intel"] = top_articles
            company["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        else:
            company["recent_intel"] = []

        time.sleep(0.2)

    # Save updated data
    with open(DATA_FILE, "w") as f:
        json.dump(companies, f, indent=2, ensure_ascii=False)
    print(f"\nData saved to {DATA_FILE}")

    # Build HTML
    html = build_html(companies)

    # Write local copy
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML written to {OUTPUT_FILE}")

    # Deploy
    print("\nDeploying to Netlify...")
    deploy_to_netlify(html)

    print(f"\n{'='*60}")
    print("Done.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
