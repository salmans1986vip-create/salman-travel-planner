"""
لمسات الذكاء الاصطناعي في الواجهة: شبكة عصبية متحركة، كرة المساعد المتوهجة،
خط تفكير المساعد أثناء بناء الخطة، وبطاقة تحليل الذكاء الاصطناعي بعد الخطة.
كل الأرقام المعروضة محسوبة فعلياً من الخطة، وليست زينة.
"""
from __future__ import annotations

import random

import streamlit as st

AI_CSS = """
<style>
  /* إخفاء الشريط الجانبي المطوي بالكامل (كان يظهر كخط عمودي في الشاشات الضيقة) */
  section[data-testid="stSidebar"] { overflow: hidden; }

  /* الشبكة العصبية خلف البطل */
  .hero .neural { position:absolute; inset:0; width:100%; height:100%; z-index:0; opacity:.55; pointer-events:none; }
  .neural line { stroke:url(#ngrad); stroke-width:1; opacity:.35; }
  .neural circle { fill:#00E5FF; filter:drop-shadow(0 0 4px #00E5FF); animation: pulse 3s ease-in-out infinite; }
  .neural circle:nth-child(3n) { fill:#B79CFF; filter:drop-shadow(0 0 4px #B79CFF); animation-delay:1s; }
  .neural circle:nth-child(4n) { animation-delay:2s; }
  .neural .signal { stroke:#00E5FF; stroke-width:2; stroke-dasharray:6 140; opacity:.9;
                    animation: flow 3.5s linear infinite; }
  @keyframes pulse { 0%,100% { opacity:.35; } 50% { opacity:1; } }
  @keyframes flow { to { stroke-dashoffset:-146; } }

  /* كرة المساعد */
  .hero-row { display:flex; align-items:center; gap:26px; }
  .orb { flex:0 0 auto; width:96px; height:96px; border-radius:50%; position:relative;
         background: radial-gradient(circle at 35% 30%, #fff 0%, #7CF6FF 18%, #00E5FF 38%, #7C4DFF 75%, #2a1a6e 100%);
         box-shadow: 0 0 30px rgba(0,229,255,.7), 0 0 70px rgba(124,77,255,.5); animation: breathe 3.2s ease-in-out infinite; }
  .orb:before, .orb:after { content:""; position:absolute; inset:-12px; border-radius:50%;
         border:1px solid rgba(0,229,255,.55); animation: ring 3.2s ease-out infinite; }
  .orb:after { animation-delay:1.6s; border-color: rgba(183,156,255,.55); }
  @keyframes breathe { 0%,100% { transform:scale(1); } 50% { transform:scale(1.06); } }
  @keyframes ring { from { transform:scale(.9); opacity:1; } to { transform:scale(1.5); opacity:0; } }

  /* سطر الكتابة الآلية */
  .typing { display:inline-block; margin-top:12px; font-weight:700; color:#7CF6FF; white-space:nowrap; overflow:hidden;
            vertical-align:bottom; border-left:2px solid #00E5FF; padding-left:4px; max-width:0;
            animation: type 3.2s steps(40) .4s forwards, caret .8s step-end infinite; }
  @keyframes type { to { max-width: 40em; } }
  @keyframes caret { 50% { border-color: transparent; } }

  /* خط تفكير المساعد */
  .pipeline { display:flex; gap:10px; flex-wrap:wrap; margin: 6px 0 18px; }
  .step { flex:1 1 150px; padding:12px 14px; border-radius:16px; border:1px solid rgba(0,229,255,.25);
          background: rgba(19,28,66,.72); color:#e7ebff; font-weight:700; font-size:.92rem; position:relative; overflow:hidden; }
  .step small { display:block; color:#AEB9D8; font-weight:500; margin-top:4px; }
  .step.run { border-color:#00E5FF; box-shadow:0 0 18px rgba(0,229,255,.35); }
  .step.run:after { content:""; position:absolute; top:0; bottom:0; width:40%; right:-40%;
          background: linear-gradient(90deg, transparent, rgba(0,229,255,.25), transparent); animation: scan 1.4s linear infinite; }
  .step.done { border-color:#48F0B0; }
  .step.done:before { content:"✓ "; color:#48F0B0; }
  @keyframes scan { to { right: 110%; } }

  /* بطاقة تحليل الذكاء الاصطناعي */
  .insight { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:12px; margin: 6px 0 20px; }
  .ins { padding:14px 16px; border-radius:18px; background: rgba(19,28,66,.72); border:1px solid rgba(183,156,255,.3); }
  .ins .v { font-size:1.7rem; font-weight:800; background: linear-gradient(90deg, #00E5FF, #B79CFF);
            -webkit-background-clip:text; background-clip:text; color:transparent; }
  .ins .l { color:#AEB9D8; font-size:.88rem; }
  .bar { height:6px; border-radius:6px; background: rgba(255,255,255,.08); margin-top:8px; overflow:hidden; }
  .bar i { display:block; height:100%; background: linear-gradient(90deg, #48F0B0, #00E5FF); border-radius:6px; }

  /* حالة النموذج في الشريط الجانبي */
  .ai-status { display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:14px;
               background: rgba(0,229,255,.06); border:1px solid rgba(0,229,255,.25); font-weight:700; }
  .dot { width:10px; height:10px; border-radius:50%; background:#48F0B0; box-shadow:0 0 10px #48F0B0;
         animation: pulse 1.6s ease-in-out infinite; }
  .dot.off { background:#FFC857; box-shadow:0 0 10px #FFC857; }
</style>
"""

STEPS = [
    ("🧠", "فهم الطلب", "تحليل الوجهة والاهتمامات"),
    ("🔎", "استرجاع الأنشطة", "من قاعدة بيانات SQLite"),
    ("✨", "النموذج يخطط", "GPT-OSS 120B عبر LangChain"),
    ("🛡️", "التحقق", "رفض أي نشاط مختلق"),
    ("🧮", "حساب الميزانية", "برمجياً لا بالنموذج"),
]


def inject_css() -> None:
    st.markdown(AI_CSS, unsafe_allow_html=True)


def _neural_svg(seed: int = 7, n: int = 26) -> str:
    """رسم شبكة عصبية عشوائية ثابتة (نفس الشكل في كل تحميل)."""
    rnd = random.Random(seed)
    pts = [(rnd.randint(10, 990), rnd.randint(10, 290)) for _ in range(n)]
    lines, signals = [], []
    for i, (x1, y1) in enumerate(pts):
        near = sorted(pts, key=lambda p: (p[0] - x1) ** 2 + (p[1] - y1) ** 2)[1:3]
        for (x2, y2) in near:
            lines.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}'/>")
            if i % 4 == 0:
                signals.append(f"<line class='signal' x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}'/>")
    dots = "".join(f"<circle cx='{x}' cy='{y}' r='{rnd.choice([2, 2.5, 3.5])}'/>" for x, y in pts)
    return ("<svg class='neural' viewBox='0 0 1000 300' preserveAspectRatio='xMidYMid slice'>"
            "<defs><linearGradient id='ngrad'><stop offset='0' stop-color='#00E5FF'/>"
            "<stop offset='1' stop-color='#7C4DFF'/></linearGradient></defs>"
            f"{''.join(lines)}{''.join(signals)}{dots}</svg>")


def ai_hero(title: str, subtitle: str, badge: str, typing: str | None = None, chips: str = "") -> None:
    typing_html = f"<div class='typing'>{typing}</div>" if typing else ""
    st.markdown(
        f"<div class='hero'>{_neural_svg()}<div class='hero-row'><div class='orb'></div><div>"
        f"<span class='badge'>{badge}</span><h1>{title}</h1><p>{subtitle}</p>{typing_html}</div></div>"
        f"{chips}</div>",
        unsafe_allow_html=True,
    )


def pipeline_html(active: int | None) -> str:
    """active=None يعني اكتملت كل المراحل."""
    cells = []
    for i, (icon, name, desc) in enumerate(STEPS):
        cls = "done" if active is None or i < active else ("run" if i == active else "")
        cells.append(f"<div class='step {cls}'>{icon} {name}<small>{desc}</small></div>")
    return f"<div class='pipeline'>{''.join(cells)}</div>"


def insight_cards(match_pct: int, n_acts: int, budget_pct: int, attempts: int, source: str) -> None:
    engine = "GPT-OSS 120B · Groq" if source == "llm" else ("مخطط احتياطي" if source == "fallback" else "خطة مستوردة")
    st.markdown(
        "<div class='section-title'>🤖 تحليل المساعد الذكي</div><div class='insight'>"
        f"<div class='ins'><div class='v'>{match_pct}%</div><div class='l'>مطابقة اهتماماتك</div>"
        f"<div class='bar'><i style='width:{match_pct}%'></i></div></div>"
        f"<div class='ins'><div class='v'>{n_acts}</div><div class='l'>نشاطاً موثقاً · 0 مختلق</div></div>"
        f"<div class='ins'><div class='v'>{budget_pct}%</div><div class='l'>من الميزانية مستخدمة</div>"
        f"<div class='bar'><i style='width:{min(budget_pct, 100)}%'></i></div></div>"
        f"<div class='ins'><div class='v'>{attempts or 1}</div><div class='l'>محاولات حتى اجتياز التحقق</div></div>"
        f"<div class='ins'><div class='v' style='font-size:1.1rem'>{engine}</div><div class='l'>محرك التخطيط</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )


def ai_status(online: bool, model: str) -> None:
    label = f"متصل · {model}" if online else "الخطة الاحتياطية"
    st.markdown(f"<div class='ai-status'><span class='dot{'' if online else ' off'}'></span>{label}</div>",
                unsafe_allow_html=True)
