from django.contrib import admin
from django.utils.html import format_html
from .models import (
    GeminiTTSConfig,
    DarijatVoice,
    DarijatDialect,
    DarijatEmotion,
    DarijatStyle,
    TTSProcessing,
)


# ─── Shared mixin for the three "option" models ──────────────────────────────

class OptionAdminMixin:
    """Shared admin config for Dialect / Emotion / Style models."""
    list_display = ('name', 'value', 'is_premium', 'premium_badge', 'is_active', 'order')
    list_filter = ('is_premium', 'is_active')
    list_editable = ('is_premium', 'is_active', 'order')
    search_fields = ('name', 'value')
    ordering = ('order', 'name')

    @admin.display(description='النوع', ordering='is_premium')
    def premium_badge(self, obj):
        if obj.is_premium:
            return format_html(
                '<span style="background:#f59e0b;color:#fff;padding:2px 8px;'
                'border-radius:12px;font-size:11px;font-weight:600;">'
                '👑 مميز</span>'
            )
        return format_html(
            '<span style="background:#10b981;color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px;font-weight:600;">'
            '🟢 مجاني</span>'
        )


# ─── Gemini TTS Config Admin ──────────────────────────────────────────────────

@admin.register(GeminiTTSConfig)
class GeminiTTSConfigAdmin(admin.ModelAdmin):
    """
    Admin for the Gemini TTS configuration table.

    Only ONE row should ever exist. The list view shows the current state;
    clicking it opens the edit form where you flip the toggle.
    """

    list_display = (
        'gemini_status_badge',
        'gemini_model',
        'fallback_gemini_voice',
        'updated_at',
    )
    readonly_fields = ('updated_at',)
    fieldsets = (
        ('🔀 التبديل بين Darijat و Gemini', {
            'fields': ('use_gemini_for_arabic',),
            'description': (
                'فعّل هذا الخيار لتوجيه جميع طلبات تحويل النص العربي إلى '
                'Gemini TTS بدلاً من Darijat. '
                'أوقف تشغيله للعودة إلى Darijat.'
            ),
        }),
        ('⚙️ إعدادات Gemini', {
            'fields': ('gemini_model', 'fallback_gemini_voice'),
            'description': (
                'النموذج: gemini-2.5-flash-preview-tts أو gemini-2.5-pro-preview-tts. '
                'الصوت الافتراضي يُستخدم عند عدم تحديد صوت Gemini لصوت داريجات معين.'
            ),
        }),
        ('📝 ملاحظة داخلية', {
            'fields': ('note', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='الحالة الحالية')
    def gemini_status_badge(self, obj):
        if obj.use_gemini_for_arabic:
            return format_html(
                '<span style="background:#8b5cf6;color:#fff;padding:4px 12px;'
                'border-radius:12px;font-size:12px;font-weight:700;">'
                '🤖 Gemini مفعّل</span>'
            )
        return format_html(
            '<span style="background:#0ea5e9;color:#fff;padding:4px 12px;'
            'border-radius:12px;font-size:12px;font-weight:700;">'
            '🔵 Darijat مفعّل</span>'
        )

    def has_add_permission(self, request):
        # Only allow one config row
        return not GeminiTTSConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False  # Don't allow deleting the config


# ─── Voice Admin ──────────────────────────────────────────────────────────────

@admin.register(DarijatVoice)
class DarijatVoiceAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'voice_name', 'accent', 'gender', 'is_premium',
        'premium_badge', 'gemini_voice_display', 'is_active', 'demo_indicator', 'order',
    )
    list_filter = ('gender', 'is_premium', 'is_active', 'accent')
    list_editable = ('is_premium', 'is_active', 'order')
    search_fields = ('name', 'voice_name', 'accent', 'gemini_voice')
    ordering = ('order', 'name')
    fieldsets = (
        ('معلومات الصوت', {
            'fields': ('name', 'voice_name', 'accent', 'gender'),
        }),
        ('🤖 ربط Gemini TTS', {
            'fields': ('gemini_voice',),
            'description': (
                'حدد اسم الصوت في Gemini الذي يقابل هذا الصوت العربي. '
                'اتركه فارغاً لاستخدام الصوت الافتراضي من إعدادات GeminiTTSConfig. '
                '<br><strong>الأصوات المتاحة:</strong> Zephyr (Bright) · Puck (Upbeat) · '
                'Charon (Informative) · Kore (Firm) · Fenrir (Excitable) · Leda (Youthful) · '
                'Aoede (Breezy) · Orus (Firm) · Sulafat (Warm) · Achird (Friendly) · '
                'Achernar (Soft) · Gacrux (Mature) · Schedar (Even) · Enceladus (Breathy) · '
                'Iapetus (Clear) · Algieba (Smooth) · Despina (Smooth) · Laomedeia (Upbeat) · '
                'Autonoe (Bright) · Callirrhoe (Easy-going) · Umbriel (Easy-going) · '
                'Erinome (Clear) · Algenib (Gravelly) · Rasalgethi (Informative) · '
                'Pulcherrima (Forward) · Zubenelgenubi (Casual) · Vindemiatrix (Gentle) · '
                'Sadachbia (Lively) · Sadaltager (Knowledgeable) · Alnilam (Firm)'
            ),
        }),
        ('الحالة', {
            'fields': ('is_premium', 'is_active', 'order'),
        }),
        ('العينة الصوتية', {
            'fields': ('demo_audio',),
            'description': 'ارفع ملف MP3 كعينة صوتية يسمعها المستخدم.',
        }),
    )

    @admin.display(description='النوع', ordering='is_premium')
    def premium_badge(self, obj):
        if obj.is_premium:
            return format_html(
                '<span style="background:#f59e0b;color:#fff;padding:2px 8px;'
                'border-radius:12px;font-size:11px;font-weight:600;">'
                '👑 مميز</span>'
            )
        return format_html(
            '<span style="background:#10b981;color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px;font-weight:600;">'
            '🟢 مجاني</span>'
        )

    @admin.display(description='صوت Gemini', ordering='gemini_voice')
    def gemini_voice_display(self, obj):
        if obj.gemini_voice:
            return format_html(
                '<span style="background:#8b5cf6;color:#fff;padding:2px 8px;'
                'border-radius:12px;font-size:11px;font-weight:600;">'
                '🤖 {}</span>',
                obj.gemini_voice,
            )
        cfg_voice = 'Zephyr'
        from .models import GeminiTTSConfig
        cfg = GeminiTTSConfig.get_config()
        if cfg:
            cfg_voice = cfg.fallback_gemini_voice
        return format_html(
            '<span style="background:#6b7280;color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px;">'
            '↩ {} (افتراضي)</span>',
            cfg_voice,
        )

    @admin.display(description='عينة', boolean=True)
    def demo_indicator(self, obj):
        return bool(obj.demo_audio)


# ─── Dialect Admin ────────────────────────────────────────────────────────────

@admin.register(DarijatDialect)
class DarijatDialectAdmin(OptionAdminMixin, admin.ModelAdmin):
    pass


# ─── Emotion Admin ────────────────────────────────────────────────────────────

@admin.register(DarijatEmotion)
class DarijatEmotionAdmin(OptionAdminMixin, admin.ModelAdmin):
    pass


# ─── Style Admin ──────────────────────────────────────────────────────────────

@admin.register(DarijatStyle)
class DarijatStyleAdmin(OptionAdminMixin, admin.ModelAdmin):
    pass


# ─── TTS Processing Admin ─────────────────────────────────────────────────────

@admin.register(TTSProcessing)
class TTSProcessingAdmin(admin.ModelAdmin):
    list_display = (
        'processing_id', 'user', 'language', 'voice_name',
        'status_badge', 'char_count', 'created_at',
    )
    list_filter = ('status', 'language', 'created_at')
    search_fields = ('processing_id', 'user__username', 'user__email', 'voice_name')
    readonly_fields = (
        'processing_id', 'user', 'language', 'text', 'voice_name',
        'style_instruction', 'openai_voice', 'openai_speed', 'openai_format',
        'celery_task_id', 'status', 'result_file', 'error_message',
        'char_count', 'created_at', 'updated_at',
    )
    ordering = ('-created_at',)

    @admin.display(description='الحالة', ordering='status')
    def status_badge(self, obj):
        colors = {
            'PENDING': ('#3b82f6', '⏳'),
            'PROCESSING': ('#f59e0b', '⚙️'),
            'COMPLETED': ('#10b981', '✅'),
            'FAILED': ('#ef4444', '❌'),
        }
        color, icon = colors.get(obj.status, ('#6b7280', '❓'))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px;font-weight:600;">'
            '{} {}</span>',
            color, icon, obj.get_status_display(),
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False