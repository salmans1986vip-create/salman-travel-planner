"""
أخطاء مخصّصة للتطبيق.

كل خطأ يحمل رسالة عربية واضحة تُعرض للمستخدم مباشرة في الواجهة،
بدلاً من إظهار تتبّع أخطاء Python التقني.
"""


class TravelPlannerError(Exception):
    """الأصل المشترك لجميع أخطاء التطبيق."""

    user_message = "حدث خطأ غير متوقع. حاول مرة أخرى."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.user_message)
        self.user_message = message or self.user_message


class InvalidInputError(TravelPlannerError):
    """مدخلات غير صالحة من المستخدم (أيام، ميزانية، وجهة...)."""

    user_message = "المدخلات غير صحيحة، راجع الحقول المظللة."


class APIUnavailableError(TravelPlannerError):
    """خدمة النموذج اللغوي غير متاحة (لا يوجد مفتاح، انقطاع، تجاوز الحد)."""

    user_message = "خدمة النموذج اللغوي غير متاحة حالياً."


class DatabaseUnavailableError(TravelPlannerError):
    """تعذّر فتح قاعدة البيانات أو الكتابة فيها."""

    user_message = "قاعدة البيانات غير متاحة حالياً."


class UnsupportedFileError(TravelPlannerError):
    """ملف مرفوع بصيغة غير مدعومة أو بمحتوى تالف."""

    user_message = "صيغة الملف غير مدعومة. يُقبل ملف JSON صادر من التطبيق فقط."


class InvalidModelResponseError(TravelPlannerError):
    """رد النموذج لا يطابق البنية المطلوبة أو يخالف البيانات."""

    user_message = "رد النموذج غير مناسب، أُعيدت المحاولة دون نجاح."
