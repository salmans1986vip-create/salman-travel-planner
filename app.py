"""
واجهة المستخدم — مساعد تخطيط السفر (Streamlit).

التشغيل:
    streamlit run app.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from travel_planner.exceptions import TravelPlannerError  # noqa: E402
from travel_planner.exporter import export_json  # noqa: E402
from travel_planner.formatting import CATEGORY_AR  # noqa: E402
from travel_planner.planner import PlanResult, TravelPlannerService  # noqa: E402
from travel_planner.schemas import SUPPORTED_INTERESTS  # noqa: E402

import ai_theme  # noqa: E402,I001  لمسات الذكاء الاصطناعي في الواجهة

st.set_page_config(page_title="مساعد تخطيط السفر", page_icon="🧳", layout="wide")

# هوية بصرية داكنة متوهجة توحي بالذكاء الاصطناعي، مع دعم كامل للاتجاه من اليمين لليسار
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');

      :root { --cyan:#00E5FF; --violet:#7C4DFF; --lilac:#B79CFF; --mint:#48F0B0;
              --bg:#070B1F; --card:rgba(19,28,66,.72); --line:rgba(0,229,255,.28); --muted:#AEB9D8; }

      html, body, [class*="css"], .stApp, .stMarkdown, .stTextInput, .stSelectbox, .stMultiSelect,
      .stNumberInput, .stSlider, .stChatMessage, .stAlert, .stTabs, .stRadio, .stCaption, label, p, h1, h2, h3, h4 {
          direction: rtl; text-align: right; font-family: 'Tajawal', sans-serif !important; }

      /* خلفية بتدرجات وشبكة نقاط خفيفة */
      .stApp {
          background:
            radial-gradient(1100px 600px at 85% -10%, rgba(124,77,255,.28), transparent 60%),
            radial-gradient(900px 500px at 5% 10%, rgba(0,229,255,.18), transparent 60%),
            radial-gradient(rgba(255,255,255,.05) 1px, transparent 1px) 0 0 / 26px 26px,
            var(--bg);
      }
      header[data-testid="stHeader"] { background: transparent; }

      /* الشريط الجانبي الزجاجي */
      section[data-testid="stSidebar"] > div {
          background: linear-gradient(180deg, rgba(17,24,58,.95), rgba(7,11,31,.95));
          border-left: 1px solid var(--line); }
      section[data-testid="stSidebar"] .stRadio label { font-size: 1.05rem; padding: 6px 2px; }

      /* البطل (Hero) */
      .hero { position: relative; padding: 34px 34px 28px; border-radius: 26px; margin: 4px 0 26px;
              background: linear-gradient(135deg, rgba(0,229,255,.10), rgba(124,77,255,.16));
              border: 1px solid var(--line); box-shadow: 0 0 40px rgba(0,229,255,.12), inset 0 0 60px rgba(124,77,255,.10);
              overflow: hidden; }
      .hero:after { content:""; position:absolute; inset:-40%; background:
              conic-gradient(from 180deg, transparent, rgba(0,229,255,.18), transparent 30%);
              animation: spin 14s linear infinite; z-index:0; opacity:.45; }
      .hero > * { position: relative; z-index: 1; }
      @keyframes spin { to { transform: rotate(360deg); } }
      .hero .badge { display:inline-block; padding:6px 14px; border-radius:999px; font-size:.85rem; font-weight:700;
              color:var(--cyan); border:1px solid var(--line); background:rgba(0,229,255,.08); margin-bottom:12px; }
      .hero h1 { margin:0; font-size: 2.6rem; font-weight: 800; line-height:1.25;
              background: linear-gradient(90deg, #fff, var(--cyan) 45%, var(--lilac));
              -webkit-background-clip: text; background-clip: text; color: transparent; }
      .hero p { color: var(--muted); font-size: 1.08rem; margin: 10px 0 0; }
      .chips { display:flex; gap:10px; flex-wrap:wrap; margin-top:18px; }
      .chip { padding:8px 14px; border-radius:14px; background:rgba(7,11,31,.55); border:1px solid rgba(183,156,255,.35);
              color:#e7ebff; font-size:.92rem; }
      .chip b { color: var(--cyan); }

      /* البطاقات */
      .day-card { border: 1px solid var(--line); border-radius: 20px; padding: 18px 22px; margin-bottom: 14px;
                  background: var(--card); backdrop-filter: blur(6px);
                  box-shadow: 0 0 24px rgba(0,229,255,.08); transition: transform .2s, box-shadow .2s; }
      .day-card:hover { transform: translateY(-2px); box-shadow: 0 0 34px rgba(0,229,255,.22); }
      .day-card h4 { margin: 0 0 10px; color: #fff; }
      .day-card h4 span { color: var(--cyan); }
      .day-card b { color: #fff; }
      .item { padding: 10px 0; border-top: 1px dashed rgba(174,185,216,.18); }
      .item:first-of-type { border-top: 0; }
      .slot { display:inline-block; min-width:70px; padding:2px 10px; margin-left:8px; border-radius:10px; font-weight:700;
              color:#070B1F; background: linear-gradient(90deg, var(--cyan), var(--lilac)); font-size:.85rem; text-align:center; }
      .muted { color: var(--muted); font-size: 0.92rem; }
      .section-title { font-size:1.35rem; font-weight:800; margin: 8px 0 12px; color:#fff; }
      .section-title:before { content:""; display:inline-block; width:10px; height:10px; border-radius:50%;
              background: var(--cyan); box-shadow: 0 0 12px var(--cyan); margin-left:10px; }

      /* عناصر Streamlit */
      div[data-testid="stForm"], div[data-testid="stMetric"], .stTable, div[data-testid="stDataFrame"] {
          background: var(--card); border: 1px solid var(--line); border-radius: 20px; }
      div[data-testid="stForm"] { padding: 22px 24px; box-shadow: 0 0 30px rgba(124,77,255,.12); }
      div[data-testid="stMetric"] { padding: 14px 16px; }
      div[data-testid="stMetricValue"] { color: var(--cyan); font-weight: 800; }
      .stButton > button, .stDownloadButton > button, div[data-testid="stFormSubmitButton"] > button {
          border-radius: 14px; border: 1px solid var(--line); font-weight: 700;
          background: rgba(0,229,255,.06); color: #fff; transition: all .2s; }
      .stButton > button:hover, .stDownloadButton > button:hover { border-color: var(--cyan); box-shadow: 0 0 18px rgba(0,229,255,.35); }
      div[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"], .stButton > button[kind="primary"] {
          background: linear-gradient(90deg, var(--cyan), var(--violet)); color: #070B1F; border: 0;
          box-shadow: 0 0 24px rgba(0,229,255,.35); }
      div[data-testid="stProgress"] > div > div > div { background: linear-gradient(90deg, var(--mint), var(--cyan)); }
      div[data-testid="stChatMessage"] { background: var(--card); border: 1px solid rgba(183,156,255,.25); border-radius: 18px; }
      .stTextInput input, .stNumberInput input, div[data-baseweb="select"] > div {
          background: rgba(7,11,31,.6) !important; border-radius: 12px !important; }
      .footer { text-align:center; color: var(--muted); font-size:.85rem; margin-top: 40px; opacity:.8; }
    </style>
    """,
    unsafe_allow_html=True,
)
ai_theme.inject_css()


def hero(title: str, subtitle: str, badge: str = "🤖 مدعوم بالذكاء الاصطناعي · LangChain + GPT-OSS 120B",
         typing: str | None = None) -> None:
    """يعرض رأس الصفحة المتوهج مع الشبكة العصبية وكرة المساعد."""
    chips = ("<div class='chips'><span class='chip'>📍 <b>3</b> وجهات</span>"
             "<span class='chip'>🎯 <b>33</b> نشاطاً موثقاً</span>"
             "<span class='chip'>🧮 ميزانية تحسب بالكود</span>"
             "<span class='chip'>💬 تعديل بالمحادثة</span></div>")
    ai_theme.ai_hero(title, subtitle, badge, typing=typing, chips=chips)


SOURCE_LABELS = {"llm": "🤖 مولّدة بالنموذج اللغوي", "fallback": "⚙️ خطة احتياطية", "imported": "📥 مستوردة"}


def _load_cloud_secret() -> None:
    """على Streamlit Cloud يوضع المفتاح في Secrets؛ ننقله لمتغيرات البيئة دون كتابته في الكود."""
    import os
    try:
        if "GROQ_API_KEY" in st.secrets and not os.getenv("GROQ_API_KEY"):
            os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
    except Exception:  # noqa: BLE001 — لا يوجد ملف أسرار محلياً
        pass


@st.cache_resource(show_spinner=False)
def get_service() -> TravelPlannerService:
    return TravelPlannerService()


def show_error(exc: Exception) -> None:
    """يعرض الأخطاء المعروفة برسالة عربية، وغير المعروفة برسالة عامة."""
    if isinstance(exc, TravelPlannerError):
        st.error(exc.user_message)
    else:
        st.error("حدث خطأ غير متوقع. أعد المحاولة، وإن تكرر راجع سجل التشغيل.")
        st.exception(exc)


def render_plan(service: TravelPlannerService, result: PlanResult) -> None:
    req = result.request
    st.markdown(f"<div class='section-title'>رحلتك إلى {req['destination']} لمدة {req['days']} أيام</div>",
                unsafe_allow_html=True)
    st.caption(f"رقم الرحلة #{result.trip_id} · {SOURCE_LABELS.get(result.source, result.source)}"
               + (f" · عدد المحاولات {result.attempts}" if result.attempts else ""))
    st.write(result.plan.summary)

    for w in result.warnings:
        st.warning(w)

    ids = [i.activity_id for d in result.plan.days for i in d.items]
    acts = service.db.get_activities_by_ids(ids)

    # بطاقة تحليل المساعد: أرقام محسوبة فعلياً من الخطة
    codes = {SUPPORTED_INTERESTS[i] for i in req.get("interests", []) if i in SUPPORTED_INTERESTS}
    matched = sum(1 for a in acts.values() if a.get("category") in codes)
    match_pct = round(100 * matched / len(acts)) if acts and codes else 100
    budget_pct = round(100 * result.budget.total / result.budget.budget) if result.budget.budget else 0
    ai_theme.insight_cards(match_pct, len(ids), budget_pct, result.attempts, result.source)

    col_plan, col_budget = st.columns([3, 2], gap="large")

    with col_plan:
        for day in result.plan.days:
            items_html = "".join(
                f"<div class='item'><span class='slot'>{it.time_slot}</span> <b>{it.activity_name}</b>"
                f" <span class='muted'>· {CATEGORY_AR.get(acts.get(it.activity_id, {}).get('category'), '')}"
                f" · {acts.get(it.activity_id, {}).get('cost_per_person', 0):g} ريال/فرد</span>"
                f"<div class='muted'>{it.reason}</div></div>"
                for it in day.items
            )
            st.markdown(f"<div class='day-card'><h4><span>اليوم {day.day_number}</span> · {day.title}</h4>{items_html}</div>",
                        unsafe_allow_html=True)
        if result.plan.tips:
            st.markdown("**نصائح:**\n" + "\n".join(f"- {t}" for t in result.plan.tips))

    with col_budget:
        b = result.budget
        st.markdown("<div class='section-title'>التكلفة التقديرية</div>", unsafe_allow_html=True)
        st.table({"البند": [line.label for line in b.lines], "المبلغ (ريال)": [f"{line.amount:,.0f}" for line in b.lines]})
        m1, m2 = st.columns(2)
        m1.metric("الإجمالي", f"{b.total:,.0f} ريال")
        m2.metric("المتبقي", f"{b.remaining:,.0f} ريال", delta=None if b.within_budget else "تجاوز")
        st.progress(min(b.total / b.budget, 1.0), text=f"{b.total / b.budget:.0%} من الميزانية")
        st.caption("التكاليف تقديرية من بيانات تجريبية، ويحسبها النظام برمجياً لا النموذج.")

        st.download_button("⬇️ تصدير نصي (.txt)", service.export_text(result),
                           file_name=f"trip_{result.trip_id}.txt", use_container_width=True)
        st.download_button("⬇️ تصدير JSON", export_json(result.request, result.plan),
                           file_name=f"trip_{result.trip_id}.json", use_container_width=True)


def render_chat(service: TravelPlannerService, result: PlanResult) -> None:
    st.divider()
    st.markdown("<div class='section-title'>💬 عدّل خطتك بالمحادثة</div>", unsafe_allow_html=True)
    st.caption("أمثلة: «اجعل اليوم الأول أخف» · «استبدل التسوق بنشاط تراثي» · «خطة أوفر»")
    for msg in service.chat_history(result.trip_id):
        is_user = msg["role"] == "human"
        with st.chat_message("user" if is_user else "assistant", avatar="🧑" if is_user else "✨"):
            st.write(msg["content"])

    prompt = st.chat_input("اكتب طلب التعديل...")
    if prompt:
        with st.spinner("✨ المساعد الذكي يعيد التفكير في خطتك..."):
            try:
                st.session_state.result = service.revise_plan(result.trip_id, prompt)
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                show_error(exc)


def page_plan(service: TravelPlannerService) -> None:
    hero("مساعد تخطيط السفر الذكي",
         "أخبرني بوجهتك وميزانيتك واهتماماتك، وسأبني لك برنامجاً يومياً دقيقاً من أنشطة حقيقية خلال ثوانٍ.",
         typing="أفهم طلبك… أسترجع الأنشطة… أخطط… أتحقق… أحسب")

    if not service.llm_available:
        st.info("لم يُضبط مفتاح GROQ_API_KEY؛ سيعمل التطبيق بالخطة الاحتياطية دون النموذج اللغوي.")

    try:
        destinations = service.db.list_destinations()
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        return

    with st.form("trip_form"):
        c1, c2, c3 = st.columns(3)
        dest = c1.selectbox("الوجهة", [d["name"] for d in destinations])
        days = c2.number_input("عدد الأيام", min_value=1, max_value=7, value=3)
        travelers = c3.number_input("عدد المسافرين", min_value=1, max_value=10, value=2)
        budget = st.number_input("الميزانية الإجمالية (ريال)", min_value=0, value=5000, step=500)
        interests = st.multiselect("الاهتمامات", list(SUPPORTED_INTERESTS), default=["تاريخ وتراث"])
        notes = st.text_input("ملاحظات (اختياري)", max_chars=300, placeholder="مثال: معنا أطفال، نفضّل بداية متأخرة")
        submitted = st.form_submit_button("✨ أنشئ الخطة", type="primary", use_container_width=True)

    if submitted:
        # خط تفكير المساعد: يعرض مراحل المعالجة الفعلية أثناء بناء الخطة
        board = st.empty()
        for step in range(2):
            board.markdown(ai_theme.pipeline_html(step), unsafe_allow_html=True)
            time.sleep(0.35)
        board.markdown(ai_theme.pipeline_html(2), unsafe_allow_html=True)
        with st.spinner("✨ المساعد الذكي يبني خطتك..."):
            try:
                st.session_state.result = service.create_plan({
                    "destination": dest, "days": days, "travelers": travelers,
                    "budget": budget, "interests": interests, "notes": notes,
                })
                board.markdown(ai_theme.pipeline_html(None), unsafe_allow_html=True)
            except Exception as exc:  # noqa: BLE001
                board.empty()
                show_error(exc)

    result: PlanResult | None = st.session_state.get("result")
    if result:
        render_plan(service, result)
        render_chat(service, result)


def page_saved(service: TravelPlannerService) -> None:
    hero("رحلاتي المحفوظة", "كل خططك في مكان واحد: افتحها، صدرها، أو احذفها.", badge="📁 الخطط المحفوظة")
    try:
        trips = service.list_trips()
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        return

    up = st.file_uploader("استيراد خطة (ملف JSON صادر من التطبيق)")
    if up is not None and st.button("استيراد"):
        try:
            st.session_state.result = service.import_plan(up.name, up.getvalue())
            st.success("تم الاستيراد والحفظ.")
        except Exception as exc:  # noqa: BLE001
            show_error(exc)

    if not trips:
        st.info("لا توجد خطط محفوظة بعد.")
        return

    st.dataframe(
        [{"#": t["id"], "الوجهة": t["destination"], "الأيام": t["days"], "المسافرون": t["travelers"],
          "الميزانية": t["budget"], "التكلفة": t["total_cost"], "المصدر": SOURCE_LABELS.get(t["source"], t["source"]),
          "آخر تحديث": t["updated_at"]} for t in trips],
        use_container_width=True, hide_index=True,
    )
    selected = st.selectbox("اختر رحلة", [t["id"] for t in trips],
                            format_func=lambda i: f"#{i} — " + next(t["destination"] for t in trips if t["id"] == i))
    c1, c2 = st.columns(2)
    if c1.button("فتح الرحلة", use_container_width=True):
        st.session_state.result = service.load_trip(selected)
        st.session_state.nav_target = "تخطيط رحلة"  # يُطبق قبل إنشاء القائمة في الدورة التالية
        st.rerun()
    if c2.button("🗑️ حذف", use_container_width=True):
        service.delete_trip(selected)
        st.session_state.pop("result", None)
        st.rerun()


def page_about(service: TravelPlannerService) -> None:
    hero("كيف يعمل المساعد؟", "نموذج لغوي مرن، وقاعدة بيانات موثوقة، وحساب برمجي دقيق في نظام واحد.", badge="ℹ️ عن النظام")
    st.markdown(
        f"""
        - **النموذج اللغوي:** `{service.settings.model_name}` عبر Groq ({'متصل' if service.llm_available else 'غير مضبوط'})
        - **التنسيق:** LangChain — ChatPromptTemplate · LCEL · PydanticOutputParser · Tools · RunnableWithMessageHistory
        - **قاعدة البيانات:** SQLite (`{service.settings.db_path.name}`)
        - **الوجهات:** {len(service.db.list_destinations())} وجهات بأنشطة وتكاليف تقديرية تجريبية
        """
    )
    st.subheader("الأنشطة المتاحة")
    dest = st.selectbox("الوجهة", [d["name"] for d in service.db.list_destinations()])
    rows = service.db.search_activities(dest)
    st.dataframe([{"#": a["id"], "النشاط": a["name"], "الفئة": CATEGORY_AR[a["category"]],
                   "المدة": a["duration_hours"], "التكلفة/فرد": a["cost_per_person"], "الوقت": a["best_time"]}
                  for a in rows], hide_index=True, use_container_width=True)


def main() -> None:
    _load_cloud_secret()
    try:
        service = get_service()
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        st.stop()

    pages = {"تخطيط رحلة": page_plan, "الخطط المحفوظة": page_saved, "عن النظام": page_about}
    if "nav_target" in st.session_state:
        st.session_state.page = st.session_state.pop("nav_target")
    with st.sidebar:
        st.markdown("<div class='section-title'>🧭 مساعد السفر</div>", unsafe_allow_html=True)
        page = st.radio("القائمة", list(pages), key="page", label_visibility="collapsed")
        st.divider()
        ai_theme.ai_status(service.llm_available, "GPT-OSS 120B")
        st.caption("مشروع مقرر أساسيات LangChain · المجموعة 12\nجامعة الأمير مساعد بن عبدالرحمن")
    pages[page](service)
    st.markdown("<div class='footer'>صنع بواسطة المجموعة 12 · مساعد تخطيط السفر الذكي</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
