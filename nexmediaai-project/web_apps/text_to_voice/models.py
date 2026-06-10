import os
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# ─── Gemini TTS configuration (singleton-style table) ────────────────────────

class GeminiTTSConfig(models.Model):
    """
    Single-row configuration table.
    When `use_gemini_for_arabic` is True, all Arabic TTS requests are routed
    to the Gemini TTS API instead of Darijat.

    Usage in code:
        cfg = GeminiTTSConfig.objects.first()
        if cfg and cfg.use_gemini_for_arabic:
            ...
    """

    use_gemini_for_arabic = models.BooleanField(
        default=False,
        verbose_name='استخدام Gemini بدلاً من Darijat',
        help_text='عند التفعيل يتم توجيه طلبات العربية إلى Gemini TTS بدلاً من Darijat.',
    )
    gemini_model = models.CharField(
        max_length=100,
        default='gemini-2.5-flash-preview-tts',
        verbose_name='نموذج Gemini',
        help_text='مثال: gemini-2.5-flash-preview-tts أو gemini-2.5-pro-preview-tts',
    )
    fallback_gemini_voice = models.CharField(
        max_length=100,
        default='Zephyr',
        verbose_name='صوت Gemini الافتراضي',
        help_text='الصوت المستخدم عندما لا يكون للصوت المطلوب مقابل محدد في Gemini.',
    )
    note = models.TextField(
        blank=True,
        default='',
        verbose_name='ملاحظة',
        help_text='ملاحظة داخلية اختيارية (سبب التبديل، تاريخ البداية…).',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'إعداد Gemini TTS'
        verbose_name_plural = 'إعدادات Gemini TTS'

    def __str__(self):
        state = '✅ Gemini مفعّل' if self.use_gemini_for_arabic else '⛔ Darijat مفعّل'
        return f'{state} — {self.gemini_model}'

    @classmethod
    def get_config(cls):
        """Return the first (and only expected) config row, or a safe default object."""
        return cls.objects.first()

    @classmethod
    def is_gemini_active(cls):
        cfg = cls.get_config()
        return bool(cfg and cfg.use_gemini_for_arabic)


# ─── Arabic voice catalogue ───────────────────────────────────────────────────

class DarijatVoice(models.Model):
    """Arabic voices available via the Darijat TTS API (or their Gemini equivalents)."""

    GENDER_CHOICES = [
        ('male', 'ذكر'),
        ('female', 'انثى'),
        ('children', 'أطفال'),
    ]

    name = models.CharField(max_length=100, verbose_name='اسم الصوت')
    voice_name = models.CharField(
        max_length=100,
        verbose_name='اسم الصوت في API',
        help_text='القيمة المرسلة إلى واجهة داريجات (voice_name)',
    )
    accent = models.CharField(max_length=100, blank=True, verbose_name='اللهجة / النبرة')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, verbose_name='الجنس')
    is_premium = models.BooleanField(default=True, verbose_name='مميز (Premium)')
    is_active = models.BooleanField(default=True, verbose_name='مفعل')
    demo_audio = models.FileField(
        upload_to='voice_demos/',
        blank=True,
        null=True,
        verbose_name='ملف العينة الصوتية',
        help_text='MP3 demo file',
    )
    order = models.IntegerField(default=0, verbose_name='الترتيب')

    # ── Gemini fallback mapping ───────────────────────────────────────────────
    gemini_voice = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='صوت Gemini المقابل',
        help_text=(
            'اسم الصوت في Gemini TTS المستخدم عند تفعيل Gemini كبديل. '
            'اتركه فارغاً لاستخدام الصوت الافتراضي من إعدادات GeminiTTSConfig. '
            'الأصوات المتاحة: Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, '
            'Aoede, Callirrhoe, Autonoe, Enceladus, Iapetus, Umbriel, Algieba, '
            'Despina, Erinome, Algenib, Rasalgethi, Laomedeia, Achernar, Alnilam, '
            'Schedar, Gacrux, Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, '
            'Sadachbia, Sadaltager, Sulafat'
        ),
    )

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'صوت داريجات'
        verbose_name_plural = 'أصوات داريجات'

    def __str__(self):
        tier = '🟢' if not self.is_premium else '👑'
        return f'{tier} {self.name} ({self.get_gender_display()})'

    @property
    def has_demo(self):
        return bool(self.demo_audio)

    def get_gemini_voice(self):
        """
        Return the Gemini voice name to use for this Darijat voice.
        Falls back to GeminiTTSConfig.fallback_gemini_voice if not set.
        """
        if self.gemini_voice.strip():
            return self.gemini_voice.strip()
        cfg = GeminiTTSConfig.get_config()
        return cfg.fallback_gemini_voice if cfg else 'Zephyr'


# ─── Dialect / Emotion / Style option tables ──────────────────────────────────

class DarijatDialect(models.Model):
    """Dialect options (اللهجة) appended to style_instruction."""

    name = models.CharField(max_length=100, verbose_name='اسم اللهجة')
    value = models.CharField(
        max_length=200,
        verbose_name='القيمة',
        help_text='القيمة المضافة إلى style_instruction مثل: لهجة قطرية',
    )
    is_premium = models.BooleanField(default=False, verbose_name='مميز (Premium)')
    is_active = models.BooleanField(default=True, verbose_name='مفعل')
    order = models.IntegerField(default=0, verbose_name='الترتيب')

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'لهجة'
        verbose_name_plural = 'اللهجات'

    def __str__(self):
        tier = '👑' if self.is_premium else '🟢'
        return f'{tier} {self.name}'


class DarijatEmotion(models.Model):
    """Emotion options (المشاعر) appended to style_instruction."""

    name = models.CharField(max_length=100, verbose_name='اسم المشاعر')
    value = models.CharField(
        max_length=200,
        verbose_name='القيمة',
        help_text='القيمة المضافة إلى style_instruction مثل: متحمس',
    )
    is_premium = models.BooleanField(default=False, verbose_name='مميز (Premium)')
    is_active = models.BooleanField(default=True, verbose_name='مفعل')
    order = models.IntegerField(default=0, verbose_name='الترتيب')

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'مشاعر'
        verbose_name_plural = 'المشاعر'

    def __str__(self):
        tier = '👑' if self.is_premium else '🟢'
        return f'{tier} {self.name}'


class DarijatStyle(models.Model):
    """Performance style options (أساليب الأداء) appended to style_instruction."""

    name = models.CharField(max_length=200, verbose_name='اسم أسلوب الأداء')
    value = models.CharField(
        max_length=300,
        verbose_name='القيمة',
        help_text='القيمة المضافة إلى style_instruction مثل: معلق صوتي',
    )
    is_premium = models.BooleanField(default=False, verbose_name='مميز (Premium)')
    is_active = models.BooleanField(default=True, verbose_name='مفعل')
    order = models.IntegerField(default=0, verbose_name='الترتيب')

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'أسلوب أداء'
        verbose_name_plural = 'أساليب الأداء'

    def __str__(self):
        tier = '👑' if self.is_premium else '🟢'
        return f'{tier} {self.name}'


# ─── TTS Processing tracker ───────────────────────────────────────────────────

class TTSProcessing(models.Model):
    """Tracks async TTS generation tasks (OpenAI, Darijat, and Gemini)."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    LANGUAGE_CHOICES = [
        ('other', 'Other Languages'),
        ('arabic', 'Arabic (Darijat)'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tts_processings')
    processing_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)

    # Request info
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES)
    text = models.TextField(verbose_name='النص المدخل')
    voice_name = models.CharField(max_length=100, verbose_name='اسم الصوت')
    style_instruction = models.TextField(blank=True, default='', verbose_name='تعليمات الأسلوب')

    # OpenAI-specific fields
    openai_voice = models.CharField(max_length=20, blank=True, default='')
    openai_speed = models.FloatField(default=1.0)
    openai_format = models.CharField(max_length=10, default='mp3')

    # Celery task tracking
    celery_task_id = models.CharField(max_length=255, blank=True, default='')

    # Status and results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    result_file = models.CharField(max_length=500, blank=True, default='', verbose_name='مسار ملف النتيجة')
    error_message = models.CharField(max_length=500, blank=True, default='')
    char_count = models.IntegerField(default=0, verbose_name='عدد الأحرف')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tts_processing'
        ordering = ['-created_at']
        verbose_name = 'معالجة تحويل نص إلى صوت'
        verbose_name_plural = 'معالجات تحويل نص إلى صوت'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['processing_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'TTS {self.processing_id} — {self.user} — {self.status}'

    def delete(self, *args, **kwargs):
        """Clean up audio file on delete."""
        if self.result_file:
            try:
                if os.path.isfile(self.result_file):
                    os.remove(self.result_file)
            except Exception:
                pass
        super().delete(*args, **kwargs)