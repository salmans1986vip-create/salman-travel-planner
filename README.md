# مساعد تخطيط السفر — AI Travel Planning Assistant

مشروع مقرر **أساسيات LangChain (LCH303)** — دبلوم الذكاء الاصطناعي التوليدي — المجموعة 12.

يبني التطبيق برنامج سفر يومياً لثلاث وجهات داخل المملكة (جدة، العلا، المدينة المنورة) وفق عدد الأيام والمسافرين
والميزانية والاهتمامات. يختار النموذج اللغوي الأنشطة **من قاعدة البيانات فقط**، ثم يتحقق النظام من الخطة
ويحسب التكلفة برمجياً، ويمكن تعديل الخطة بالمحادثة وحفظها وتصديرها.

## التقنيات
| المكون | التقنية |
|---|---|
| الواجهة | Streamlit |
| التنسيق | LangChain (ChatPromptTemplate، LCEL، PydanticOutputParser، StructuredTool، RunnableWithMessageHistory) |
| النموذج | GPT-OSS 120B عبر Groq (`langchain-groq`) |
| قاعدة البيانات | SQLite |

## هيكل المشروع
```
travel_planner/
├── app.py                     واجهة Streamlit
├── requirements.txt
├── .env.example               نموذج ملف المفاتيح
├── src/travel_planner/
│   ├── config.py              الإعدادات وقراءة .env
│   ├── exceptions.py          أخطاء مخصصة برسائل عربية
│   ├── schemas.py             نماذج Pydantic (الطلب والخطة والميزانية)
│   ├── seed_data.py           بيانات الوجهات والأنشطة التجريبية
│   ├── database.py            طبقة SQLite (5 جداول)
│   ├── budget.py              حساب التكلفة برمجياً
│   ├── validation.py          التحقق من المدخلات ومن خطة النموذج
│   ├── formatting.py          تجهيز جدول الأنشطة والتصدير النصي
│   ├── prompts.py             قوالب التعليمات (Prompt Engineering)
│   ├── tools.py               أدوات LangChain: البحث، الميزانية، الحفظ
│   ├── chains.py              سلاسل LCEL والذاكرة الدائمة
│   ├── llm.py                 ربط Groq وترجمة أخطائه
│   ├── fallback.py            مخطِّط احتياطي عند تعذر النموذج
│   ├── exporter.py            تصدير/استيراد JSON ورفض الملفات غير المدعومة
│   └── planner.py             خدمة التنسيق الرئيسية
└── tests/                     اختبارات pytest (المنطق + LangChain بنموذج وهمي)
```

## التشغيل محلياً
```bash
pip install -r requirements.txt
cp .env.example .env          # ثم ضع مفتاح Groq من https://console.groq.com/keys
pytest -q                     # تشغيل الاختبارات
streamlit run app.py
```
بدون مفتاح يعمل التطبيق بالخطة الاحتياطية، ويوضح ذلك للمستخدم.

## التشغيل على Google Colab
افتح الدفتر `Travel_Planner_Colab.ipynb` (كل خطوة من المشروع في خلية مستقلة مع شرح وتجربة)، وأضف المفتاح في **Secrets** باسم `GROQ_API_KEY`، ثم شغّل الخلايا بالترتيب.

## المكتبات والأدوات الخارجية
LangChain Core، LangChain Groq، Groq API، Streamlit، Pydantic، python-dotenv، SQLite، pytest،
و cloudflared (في Colab فقط لفتح رابط عام للواجهة).

> جميع التكاليف تقديرية من بيانات تجريبية للنموذج الأولي، ولا تمثل أسعاراً رسمية.
