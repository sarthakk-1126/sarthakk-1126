#!/usr/bin/env python3
"""Draws three SVGs for my GitHub profile README (stdlib only):

  assets/commit-candles.svg  my contribution history as a weekly stock candlestick chart
  assets/ticker.svg          a scrolling ticker tape of real numbers from my GitHub activity
  assets/status.svg          a status board that checks my public products

Chart: "price" = contributions in the trailing 7 days; one candle per week
       (open = first day, close = last day, wick = high/low of the week); green = week ended higher.
       The chart starts at my first week of activity ("IPO"); the dashed line is a 4-week average.
Status: amber on the first failed or slow check, red only after two failed checks in a row.

Env: GH_TOKEN (personal access token, read:user, so private contributions are counted), GH_LOGIN.
Flags: --demo (synthetic GitHub numbers, watermarked), --no-status, --out-dir DIR.
"""
import json, os, random, re, sys, time, urllib.request
from datetime import date, datetime, timedelta, timezone

BG, PANEL, GRID, TXT, MUTED = "#0d1117", "#161b22", "#21262d", "#e6edf3", "#7d8590"
UP, DOWN, AMBER, BLUE = "#3fb950", "#f85149", "#d29922", "#58a6ff"
FONT = "<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace}</style>"
IST = timezone(timedelta(hours=5, minutes=30))
PRODUCTS = [("Screener", "/screener/"), ("Charts", "/charts/"), ("F&amp;O", "/futures-and-options/"), ("Commentary", "/commentary/"), ("Crypto", "/crypto/")]
BASE = "https://marketdeck.in"
SLOW_MS = 8000  # the check runs from a US data centre, so a few seconds is normal
QUERY = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to){
totalCommitContributions totalPullRequestContributions totalPullRequestReviewContributions totalRepositoriesWithContributedCommits
contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;")


def fetch(login, token):
    end = date.today(); start = end - timedelta(days=364)
    body = json.dumps({"query": QUERY, "variables": {"login": login, "from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-art"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in data:
        raise SystemExit(f"GitHub API error: {data['errors']}")
    cc = data["data"]["user"]["contributionsCollection"]
    days = {d["date"]: d["contributionCount"] for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]}
    stats = {"total": cc["contributionCalendar"]["totalContributions"], "commits": cc["totalCommitContributions"], "prs": cc["totalPullRequestContributions"],
             "reviews": cc["totalPullRequestReviewContributions"], "repos": cc["totalRepositoriesWithContributedCommits"]}
    return days, stats


def demo():
    rnd = random.Random(7); end = date.today(); days = {}
    for i in range(364, -1, -1):
        d = end - timedelta(days=i)
        days[str(d)] = 0 if i > 80 else (0 if rnd.random() < .2 else int(rnd.random() ** 2 * 60))
    return days, {"total": sum(days.values()), "commits": 340, "prs": 103, "reviews": 18, "repos": 4}


def streak(days):
    keys = sorted(days); n = 0
    i = len(keys) - 1
    if days[keys[i]] == 0: i -= 1  # today may not have started yet
    while i >= 0 and days[keys[i]] > 0: n += 1; i -= 1
    return n


def candles(days):
    keys = sorted(days); series = {k: sum(days[x] for x in keys[max(0, j - 6):j + 1]) for j, k in enumerate(keys)}
    out = []
    for i in range(7, len(keys) - 6, 7):
        wk = keys[i:i + 7]; v = [series[k] for k in wk]
        out.append({"label": wk[0], "o": v[0], "c": v[-1], "h": max(v), "l": min(v), "v": sum(days[k] for k in wk)})
    first = next((i for i, c in enumerate(out) if c["v"] > 0), 0)
    return out[min(first, max(0, len(out) - 10)):]  # start at first activity, but keep at least 10 weeks


def chart_svg(cs, login, is_demo):
    W, H = 920, 360; left, right, top, base, vol = 56, 28, 66, 262, 322
    hi = max(c["h"] for c in cs) * 1.08 or 1; vmax = max(c["v"] for c in cs) or 1
    step = (W - left - right) / len(cs); bw = min(26, step * 0.6)
    y = lambda v: base - (v / hi) * (base - top)
    last, prev = cs[-1]["c"], cs[-2]["c"]; diff = last - prev
    col = UP if diff >= 0 else DOWN
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Weekly candlestick chart of {login} GitHub contributions since the first commit">{FONT}',
         f'<rect width="{W}" height="{H}" rx="12" fill="{BG}" stroke="{GRID}"/>']
    for g in range(5):
        gv = hi * g / 4
        p.append(f'<line x1="{left}" x2="{W-right}" y1="{y(gv):.1f}" y2="{y(gv):.1f}" stroke="{GRID}"/><text x="{left-8}" y="{y(gv)+4:.1f}" font-size="10" fill="{MUTED}" text-anchor="end">{gv:.0f}</text>')
    p.append(f'<text x="{left}" y="32" font-size="16" font-weight="700" fill="{TXT}">{esc(login.upper())} · COMMITS/7D</text>')
    p.append(f'<text x="{left+340}" y="32" font-size="16" fill="{col}">{last}  {"▲" if diff>=0 else "▼"} {diff:+d} w/w</text>')
    p.append(f'<text x="{W-right}" y="32" font-size="11" fill="{MUTED}" text-anchor="end">WEEKLY · SINCE FIRST COMMIT · {len(cs)} WEEKS</text>')
    ath = max(range(len(cs)), key=lambda i: cs[i]["h"]); avg = []
    for i, c in enumerate(cs):
        x = left + step * i + step / 2; cc = UP if c["c"] >= c["o"] else DOWN
        tb, bb = y(max(c["o"], c["c"])), y(min(c["o"], c["c"]))
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y(c["h"]):.1f}" y2="{y(c["l"]):.1f}" stroke="{cc}" stroke-width="1.5"/>')
        p.append(f'<rect x="{x-bw/2:.1f}" y="{tb:.1f}" width="{bw:.1f}" height="{max(1.5,bb-tb):.1f}" fill="{cc}"><title>week of {c["label"]}: open {c["o"]}, close {c["c"]}, high {c["h"]}, low {c["l"]}, total {c["v"]}</title></rect>')
        vh = c["v"] / vmax * 40
        p.append(f'<rect x="{x-bw/2:.1f}" y="{vol-vh:.1f}" width="{bw:.1f}" height="{vh:.1f}" fill="{cc}" opacity="0.35"/>')
        w4 = [k["c"] for k in cs[max(0, i - 3):i + 1]]; avg.append((x, sum(w4) / len(w4)))
    p.append(f'<polyline fill="none" stroke="{AMBER}" stroke-width="2" stroke-dasharray="5 4" points="' + " ".join(f"{x:.1f},{y(v):.1f}" for x, v in avg) + '"/>')
    ax = left + step * ath + step / 2
    p.append(f'<text x="{ax:.1f}" y="{max(50,y(cs[ath]["h"])-8):.1f}" font-size="11" fill="{AMBER}" text-anchor="middle">ATH {cs[ath]["h"]}</text>')
    p.append(f'<line x1="{left}" x2="{left}" y1="{top-6}" y2="{base}" stroke="{BLUE}" stroke-dasharray="3 3"/><text x="{left+6}" y="{top+6}" font-size="11" fill="{BLUE}">IPO · {cs[0]["label"]}</text>')
    p.append(f'<text x="{left}" y="{vol+18}" font-size="10" fill="{MUTED}">price = contributions in trailing 7 days · dashed line = 4-week average · bars = weekly volume</text>')
    p.append(f'<text x="{W-right}" y="{vol+18}" font-size="10" fill="{MUTED}" text-anchor="end">{cs[-1]["label"]}</text>')
    if is_demo:
        p.append(f'<text x="{W/2}" y="{(top+base)/2:.0f}" font-size="64" font-weight="700" fill="#fff" opacity="0.07" text-anchor="middle">DEMO DATA</text>')
    return "\n".join(p) + "</svg>"


def ticker_svg(stats, st, up_count, total_products):
    W, H = 920, 44
    items = [("CONTRIBUTIONS 52W", f'{stats["total"]:,}', UP), ("COMMITS", f'{stats["commits"]:,}', UP), ("PRS OPENED", f'{stats["prs"]:,}', UP),
             ("REVIEWS", f'{stats["reviews"]:,}', BLUE), ("REPOS", str(stats["repos"]), TXT), ("STREAK", f"{st}d", UP if st else MUTED),
             ("MARKETDECK", f"● {up_count}/{total_products} UP", UP if up_count == total_products else AMBER)]
    cw = 8.4; x = 24; row = []
    for a, b, c in items:
        row.append((x, f'<text x="{{X1}}" y="27" font-size="13" fill="{MUTED}">{a}</text><text x="{{X2}}" y="27" font-size="13" font-weight="700" fill="{c}">{esc(b)}</text>', len(a)))
        x += (len(a) + len(b)) * cw + 62
    S = x - 24
    def build(offset):
        return "".join(t.replace("{X1}", f"{x0+offset:.0f}").replace("{X2}", f"{x0+offset+n*cw+10:.0f}") for x0, t, n in row)
    g = build(0) + build(S)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Ticker tape of GitHub activity numbers">{FONT}'
            f'<defs><clipPath id="c"><rect width="{W}" height="{H}" rx="10"/></clipPath></defs><rect width="{W}" height="{H}" rx="10" fill="{BG}" stroke="{GRID}"/>'
            f'<g clip-path="url(#c)"><g><animateTransform attributeName="transform" type="translate" from="0 0" to="-{S:.0f} 0" dur="{max(18, S/45):.0f}s" repeatCount="indefinite"/>{g}</g></g></svg>')


def check(path):
    t = time.time()
    try:
        req = urllib.request.Request(BASE + path, headers={"User-Agent": "marketdeck-profile-status-check"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status < 400, int((time.time() - t) * 1000), r.status
    except Exception as e:
        return False, int((time.time() - t) * 1000), getattr(e, "code", 0)


def status_svg(results, now):
    W, H = 920, 150
    up = sum(1 for r in results if r["state"] == "up")
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Status of MarketDeck products">{FONT}',
         f'<rect width="{W}" height="{H}" rx="12" fill="{BG}" stroke="{GRID}"/>',
         f'<text x="24" y="30" font-size="14" font-weight="700" fill="{TXT}">PRODUCT STATUS</text><text x="170" y="30" font-size="13" fill="{UP if up==len(results) else AMBER}">{up}/{len(results)} operational</text>',
         f'<text x="{W-24}" y="30" font-size="11" fill="{MUTED}" text-anchor="end">checked {now:%d %b %H:%M} IST · marketdeck.in</text>']
    w = (W - 24 * 2 - 12 * (len(results) - 1)) / len(results)
    for i, r in enumerate(results):
        x = 24 + i * (w + 12)
        c = {"up": UP, "slow": AMBER, "check": AMBER, "down": DOWN}[r["state"]]
        label = {"up": f'{r["code"]} OK · {r["ms"]} ms', "slow": f'{r["code"]} slow · {r["ms"]} ms', "check": "unreachable · retrying", "down": "down"}[r["state"]]
        pulse = '<animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/>' if r["state"] == "up" else ""
        p.append(f'<rect x="{x:.0f}" y="50" width="{w:.0f}" height="78" rx="10" fill="{PANEL}" stroke="{GRID}"/><circle cx="{x+18:.0f}" cy="74" r="5" fill="{c}">{pulse}</circle>'
                 f'<text x="{x+32:.0f}" y="79" font-size="14" font-weight="700" fill="{TXT}">{r["name"]}</text><text x="{x+16:.0f}" y="100" font-size="11" fill="{MUTED}">{esc(r["path"])}</text><text x="{x+16:.0f}" y="118" font-size="11" fill="{c}">{label}</text>')
    return "\n".join(p) + "</svg>"


def run_status(out_dir):
    state_path = os.path.join(out_dir, "status-state.json")
    try: state = json.load(open(state_path))
    except Exception: state = {}
    results = []
    for name, path in PRODUCTS:
        ok, ms, code = check(path)
        fails = 0 if ok else state.get(path, 0) + 1
        state[path] = fails
        s = ("up" if ms < SLOW_MS else "slow") if ok else ("check" if fails < 2 else "down")
        results.append({"name": name, "path": path, "ms": ms, "code": code, "state": s})
    json.dump(state, open(state_path, "w"), indent=1)
    return results


if __name__ == "__main__":
    a = sys.argv; is_demo = "--demo" in a
    out_dir = a[a.index("--out-dir") + 1] if "--out-dir" in a else "assets"
    os.makedirs(out_dir, exist_ok=True)
    login = os.environ.get("GH_LOGIN", "sarthakk-1126")
    days, stats = demo() if is_demo else fetch(login, os.environ["GH_TOKEN"])
    cs = candles(days)
    if len(cs) < 3: raise SystemExit("not enough data to draw")
    if "--no-status" in a:
        results = [{"name": n, "path": p, "ms": 0, "code": 200, "state": "up"} for n, p in PRODUCTS]
    else:
        results = run_status(out_dir)
    now = datetime.now(IST); up = sum(1 for r in results if r["state"] == "up")
    open(os.path.join(out_dir, "commit-candles.svg"), "w", encoding="utf-8").write(chart_svg(cs, login, is_demo))
    open(os.path.join(out_dir, "ticker.svg"), "w", encoding="utf-8").write(ticker_svg(stats, streak(days), up, len(results)))
    open(os.path.join(out_dir, "status.svg"), "w", encoding="utf-8").write(status_svg(results, now))
    print("wrote 3 svgs;", ", ".join(f'{r["name"]}={r["state"]}({r["ms"]}ms)' for r in results))
