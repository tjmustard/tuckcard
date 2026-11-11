"""Original Tuckcard layout prototypes (MIT). Writes standalone HTML for each layout in light and dark,
and renders PNGs when Playwright and Chrome are available. Visual source for M3; not production code."""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
GOOGLE_FONTS = ("https://fonts.googleapis.com/css2?family=Archivo+Black&family=Atkinson+Hyperlegible:wght@400;700"
                "&family=Caveat:wght@400;600&family=Fraunces:wght@600&family=Literata:wght@400"
                "&family=Shantell+Sans:wght@400;600&family=Source+Serif+4:wght@400&display=swap")

CARD = {
    'n': 42, 'cat': 'Growth', 'pill': 'Kid',
    'title': ('The power of', 'yet'),
    'lines': [
        ("You can't do it ", 'yet', '.', "Add “yet” after every “I can’t.”"),
        ("That’s not the same as can’t.", None, '', None),
        ('', 'Practice', ' a bit each day,', 'Ten minutes, every single day.'),
        ("and when you’re stuck, ", 'ask', '.', 'Asking for help is a strong move.'),
        ('', '“Got it”', ' is on its way.', 'What used to be hard for you?'),
    ],
}

THEMES = {
    'light': {'bg': '#ffffff', 'ink': '#1d1d1f', 'muted': '#6b6b70', 'accent': '#c2650a', 'tint': '#fbe3c8', 'rule': '#e8e2da'},
    'dark':  {'bg': '#24211e', 'ink': '#f4efe7', 'muted': '#a9a39a', 'accent': '#f2a54a', 'tint': '#5a3e1f', 'rule': '#3a3530'},
}

def num_badge(i, t):
    return (f"<span style=\"display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;"
            f"border-radius:50%;background:{t['accent']};color:{t['bg']};font:700 10px 'Atkinson Hyperlegible';"
            f"vertical-align:super;margin-left:2px\">{i}</span>")

def notebook(t):
    """Notebook: left-aligned, highlighter marks, numbered notes in a right margin column."""
    rows, k = [], 0
    for pre, mark, post, note in CARD['lines']:
        if mark:
            k += 1
            txt = (f"{pre}<span style=\"background:linear-gradient(transparent 52%, {t['tint']} 52%, {t['tint']} 92%, transparent 92%);"
                   f"padding:0 2px\">{mark}</span>{num_badge(k, t)}{post}")
            nt = (f"<span style=\"color:{t['accent']};font-weight:600\">{k}</span>&nbsp; {note}")
        else:
            txt, nt = pre, ''
        rows.append(f"<div style='display:contents'><div style='font:400 18px/1.45 Literata;padding:9px 0'>{txt}</div>"
                    f"<div style=\"font:400 18px/1.05 Caveat;color:{t['ink']};padding:10px 0 0\">{nt}</div></div>")
    tt = CARD['title']
    return f"""
<div class=card style="background:{t['bg']};color:{t['ink']};padding:30px 28px 24px 46px;position:relative">
 <div style="position:absolute;left:30px;top:0;bottom:0;width:1.5px;background:{t['accent']};opacity:.5"></div>
 <div style="display:flex;justify-content:space-between;font:700 11px 'Atkinson Hyperlegible';letter-spacing:1.6px;text-transform:uppercase;color:{t['muted']}">
  <span>{CARD['cat']} &middot; {CARD['pill']}</span><span style="font:600 22px Fraunces;letter-spacing:0;color:{t['accent']}">{CARD['n']}</span></div>
 <div style="font:600 38px/1.05 Fraunces;margin:6px 0 16px">{tt[0]} <span style="background:linear-gradient(transparent 55%, {t['tint']} 55%)">{tt[1]}</span></div>
 <div style="display:grid;grid-template-columns:268px 1fr;column-gap:16px;align-items:start">{''.join(rows)}</div>
</div>"""

def index_card(t):
    """Index card: colored header band, plain statement, numbered 'try this' list."""
    body, items, k = [], [], 0
    for pre, mark, post, note in CARD['lines']:
        if mark:
            k += 1
            body.append(f"{pre}<b style=\"border-bottom:2.5px solid {t['accent']}\">{mark}</b>{num_badge(k, t)}{post}")
            items.append(f"<div style='display:flex;gap:9px;align-items:baseline'>"
                         f"<span style=\"flex:none;width:17px;height:17px;border-radius:4px;background:{t['accent']};color:{t['bg']};"
                         f"font:700 11px/17px 'Atkinson Hyperlegible';text-align:center\">{k}</span><span>{note}</span></div>")
        else:
            body.append(pre)
    band_ink = '#ffffff'
    return f"""
<div class=card style="background:{t['bg']};color:{t['ink']};display:flex;flex-direction:column">
 <div style="background:{t['accent']};color:{band_ink};padding:20px 28px 18px">
  <div style="display:flex;justify-content:space-between;font:700 11px 'Atkinson Hyperlegible';letter-spacing:1.6px;text-transform:uppercase;opacity:.85">
   <span>{CARD['cat']} &middot; {CARD['pill']}</span><span>No. {CARD['n']}</span></div>
  <div style="font:700 34px/1.1 'Atkinson Hyperlegible';margin-top:8px">{CARD['title'][0]} {CARD['title'][1]}</div>
 </div>
 <div style="padding:26px 28px 0;font:400 20px/1.65 'Atkinson Hyperlegible'">{'<br>'.join(body)}</div>
 <div style="margin:auto 28px 22px;padding-top:12px;border-top:1.5px solid {t['rule']};display:grid;grid-template-columns:1fr 1fr;gap:8px 18px;font:400 12.5px/1.3 'Atkinson Hyperlegible'">
  <div style="grid-column:1/-1;font:700 11px 'Atkinson Hyperlegible';letter-spacing:1.6px;text-transform:uppercase;color:{t['muted']}">Try this</div>
  {''.join(items)}</div>
</div>"""

def stacked(t):
    """Stacked: big number, title with hand-drawn swash, each note tucked under its line."""
    rows = []
    for pre, mark, post, note in CARD['lines']:
        if mark:
            m = (f"<span style='position:relative;display:inline-block'>{mark}"
                 f"<svg viewBox='0 0 100 10' preserveAspectRatio='none' style='position:absolute;left:-2px;bottom:-6px;width:calc(100% + 4px);height:8px;overflow:visible'>"
                 f"<path d='M2 7 C 30 2, 60 3, 98 5' fill='none' stroke='{t['accent']}' stroke-width='2.4' stroke-linecap='round' vector-effect='non-scaling-stroke'/></svg></span>")
            rows.append(f"<div style='font:400 19.5px/1.35 \"Source Serif 4\";margin-top:12px'>{pre}{m}{post}</div>")
            rows.append(f"<div style=\"font:400 13.5px/1.25 'Shantell Sans';color:{t['accent']};padding-left:18px;margin-top:3px\">↳ {note}</div>")
        else:
            rows.append(f"<div style='font:400 19.5px/1.35 \"Source Serif 4\";margin-top:12px'>{pre}</div>")
    return f"""
<div class=card style="background:{t['bg']};color:{t['ink']};padding:28px 30px 24px;position:relative">
 <div style="position:absolute;right:26px;top:16px;font:400 64px/1 'Archivo Black';color:{t['rule']}">{CARD['n']}</div>
 <div style="position:relative;font:700 11px 'Atkinson Hyperlegible';letter-spacing:1.6px;text-transform:uppercase;color:{t['muted']}">{CARD['cat']} &middot; {CARD['pill']}</div>
 <div style="position:relative;font:400 33px/1.08 'Archivo Black';margin:8px 0 6px;max-width:300px">{CARD['title'][0]} {CARD['title'][1]}.</div>
 <div style="position:relative">{''.join(rows)}</div>
</div>"""

def page(inner):
    return (f"<!doctype html><html><head><meta charset=utf-8><link rel=stylesheet href=\"{GOOGLE_FONTS}\"><style>"
            "body{margin:0;background:#888}.card{width:480px;height:480px;box-sizing:border-box;overflow:hidden}"
            f"</style></head><body>{inner}</body></html>")

if __name__ == '__main__':
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 480, 'height': 480}, device_scale_factor=2)
        for name, fn in [('stacked', stacked), ('notebook', notebook), ('index', index_card)]:
            for th in ('light', 'dark'):
                path = os.path.join(HERE, f'{name}-{th}.html')
                open(path, 'w').write(page(fn(THEMES[th])))
                pg.goto('file://' + path)
                pg.evaluate('document.fonts.ready')
                pg.wait_for_timeout(300)
                over = pg.evaluate("(()=>{const c=document.querySelector('.card');return c.scrollHeight>c.clientHeight+1})()")
                print(name, th, 'overflow' if over else 'fits')
                pg.locator('.card').screenshot(path=os.path.join(HERE, f'{name}-{th}.png'))
        b.close()
