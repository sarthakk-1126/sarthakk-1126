#!/usr/bin/env python3
"""Draw my GitHub contribution history as a stock candlestick chart (SVG).

"Price"  = contributions in the trailing 7 days.
Candle   = one calendar week: open = price on its first day, close = price on its last day,
           wick = highest / lowest price that week. Green = the week ended higher than it began.
Volume   = total contributions that week.

Needs env GH_TOKEN (a personal access token with read:user so private contributions are counted)
and GH_LOGIN. Stdlib only. `--demo` draws synthetic data with a DEMO watermark (for previews).
"""
import json, os, random, sys, urllib.request
from datetime import date, timedelta

W, H = 920, 360
BG, GRID, TXT, MUTED = "#0d1117", "#21262d", "#e6edf3", "#7d8590"
UP, DOWN = "#3fb950", "#f85149"
QUERY = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""


def fetch_days(login, token):
    end = date.today()
    start = end - timedelta(days=364)
    body = json.dumps({"query": QUERY, "variables": {"login": login, "from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "candles"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in data:
        raise SystemExit(f"GitHub API error: {data['errors']}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def demo_days():
    rnd = random.Random(7)
    end = date.today()
    out = {}
    for i in range(364, -1, -1):
        day = end - timedelta(days=i)
        ramp = 1 + (364 - i) / 90
        out[str(day)] = 0 if rnd.random() < 0.25 else int(rnd.random() ** 2 * 12 * ramp)
    return out


def candles(days):
    keys = sorted(days)
    series = {}
    for i, k in enumerate(keys):
        series[k] = sum(days[x] for x in keys[max(0, i - 6):i + 1])
    out = []
    for i in range(7, len(keys) - 6, 7):  # skip first partial window
        wk = keys[i:i + 7]
        vals = [series[k] for k in wk]
        out.append({"label": wk[0], "o": vals[0], "c": vals[-1], "h": max(vals), "l": min(vals), "v": sum(days[k] for k in wk)})
    return out


def render(cs, login, demo):
    left, right, top, mid = 54, 24, 58, 250
    bottom_vol = 318
    hi = max(c["h"] for c in cs) or 1
    vmax = max(c["v"] for c in cs) or 1
    step = (W - left - right) / len(cs)
    bw = max(3, step * 0.6)
    y = lambda v: mid - (v / hi) * (mid - top)
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Weekly candlestick chart of {login}\'s GitHub contributions over the last year">',
         f'<rect width="{W}" height="{H}" rx="12" fill="{BG}" stroke="{GRID}"/>',
         '<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}</style>']
    for g in range(5):
        gv = hi * g / 4
        p.append(f'<line x1="{left}" x2="{W-right}" y1="{y(gv):.1f}" y2="{y(gv):.1f}" stroke="{GRID}"/>')
        p.append(f'<text x="{left-8}" y="{y(gv)+4:.1f}" font-size="10" fill="{MUTED}" text-anchor="end">{gv:.0f}</text>')
    last, prev = cs[-1]["c"], cs[-2]["c"]
    chg = 0 if prev == 0 else (last - prev) / prev * 100
    colour = UP if last >= prev else DOWN
    p.append(f'<text x="{left}" y="30" font-size="16" font-weight="700" fill="{TXT}">{login.upper()} · COMMITS/7D</text>')
    p.append(f'<text x="{left+330}" y="30" font-size="16" fill="{colour}">{last}  {"▲" if last>=prev else "▼"} {abs(chg):.0f}% w/w</text>')
    p.append(f'<text x="{W-right}" y="30" font-size="11" fill="{MUTED}" text-anchor="end">WEEKLY · LAST 52 WEEKS</text>')
    for i, c in enumerate(cs):
        x = left + step * i + step / 2
        col = UP if c["c"] >= c["o"] else DOWN
        top_b, bot_b = y(max(c["o"], c["c"])), y(min(c["o"], c["c"]))
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y(c["h"]):.1f}" y2="{y(c["l"]):.1f}" stroke="{col}" stroke-width="1.4"/>')
        p.append(f'<rect x="{x-bw/2:.1f}" y="{top_b:.1f}" width="{bw:.1f}" height="{max(1.5,bot_b-top_b):.1f}" fill="{col}"><title>week of {c["label"]}: open {c["o"]}, close {c["c"]}, high {c["h"]}, low {c["l"]}, total {c["v"]}</title></rect>')
        vh = c["v"] / vmax * 44
        p.append(f'<rect x="{x-bw/2:.1f}" y="{bottom_vol-vh:.1f}" width="{bw:.1f}" height="{vh:.1f}" fill="{col}" opacity="0.35"/>')
    p.append(f'<text x="{left}" y="{bottom_vol+16}" font-size="10" fill="{MUTED}">{cs[0]["label"]}</text>')
    p.append(f'<text x="{W-right}" y="{bottom_vol+16}" font-size="10" fill="{MUTED}" text-anchor="end">{cs[-1]["label"]}</text>')
    p.append(f'<text x="{W/2}" y="{bottom_vol+16}" font-size="10" fill="{MUTED}" text-anchor="middle">price = contributions in trailing 7 days · volume = weekly total</text>')
    if demo:
        p.append(f'<text x="{W/2}" y="{(top+mid)/2:.0f}" font-size="64" font-weight="700" fill="#ffffff" opacity="0.08" text-anchor="middle">DEMO DATA</text>')
    p.append('</svg>')
    return "\n".join(p)


if __name__ == "__main__":
    demo = "--demo" in sys.argv
    login = os.environ.get("GH_LOGIN", "sarthakk-1126")
    days = demo_days() if demo else fetch_days(login, os.environ["GH_TOKEN"])
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "assets/commit-candles.svg"
    cs = candles(days)
    if len(cs) < 3:
        raise SystemExit("not enough data to draw")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    open(out, "w", encoding="utf-8").write(render(cs, login, demo))
    print(f"wrote {out}: {len(cs)} candles")
