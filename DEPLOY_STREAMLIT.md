# نشر المساعد على الإنترنت (رابط للعرض أمام الدكتور)

النشر مجاني على **Streamlit Community Cloud** ويأخذ تقريباً 10 دقائق.

## 1) ارفع المشروع على GitHub
1. ادخل github.com بحسابك (حساب سلمان) وأنشئ مستودعاً جديداً باسم `travel-planner` (Public).
2. ارفع كل محتويات مجلد `travel_planner` (فيها `app.py` و `src` و `requirements.txt` و `.streamlit`).
3. **لا ترفع ملف `.env`** (موجود في `.gitignore` أصلاً).

## 2) انشر التطبيق
1. ادخل share.streamlit.io وسجل دخول بحساب GitHub.
2. اضغط **Create app** ← اختر المستودع `travel-planner` والفرع `main` والملف `app.py`.
3. من **Advanced settings** ← **Secrets** الصق السطر التالي بمفتاحك:
   ```
   GROQ_API_KEY = "ضع_مفتاحك_هنا"
   ```
4. في خانة **App URL** اكتب: `salman-travel-planner` حتى يطابق الرابط المكتوب في العرض:
   `https://salman-travel-planner.streamlit.app`
5. اضغط **Deploy** وانتظر دقيقتين.

> إذا كان الاسم محجوزاً اختر اسماً آخر، وعدل الرابط في الشريحة 22 من عرض Canva.

## التشغيل المحلي (بديل وقت العرض)
```
pip install -r requirements.txt
streamlit run app.py
```
بدون مفتاح يعمل التطبيق بالخطة الاحتياطية، فالعرض ما يتعطل حتى لو انقطع الإنترنت.
