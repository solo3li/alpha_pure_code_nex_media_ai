/* =================================================
   Language Switcher — JS behaviour
   - Toggles the dropdown
   - Sets dir="rtl" / dir="ltr" on <html>
   - Loads Arabic font dynamically when needed
   ================================================= */
(function () {
    'use strict';

    // ── Helpers ─────────────────────────────────────
    function getCookie(name) {
        const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
        return v ? decodeURIComponent(v[2]) : null;
    }

    // ── RTL ─────────────────────────────────────────
    function applyDirection(lang) {
        const rtlLangs = ['ar', 'he', 'fa', 'ur'];
        const dir = rtlLangs.includes(lang) ? 'rtl' : 'ltr';
        document.documentElement.setAttribute('dir', dir);
        document.documentElement.setAttribute('lang', lang);

        if (dir === 'rtl') {
            loadArabicFont();
        }
    }

    function loadArabicFont() {
        const id = 'arabic-font-link';
        if (document.getElementById(id)) return;
        const link = document.createElement('link');
        link.id = id;
        link.rel = 'stylesheet';
        link.href = 'https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800&family=Tajawal:wght@300;400;500;700&display=swap';
        document.head.appendChild(link);
    }

    // ── Dropdown toggle ─────────────────────────────
    function initSwitcher() {
        const switchers = document.querySelectorAll('.lang-switcher');

        switchers.forEach(container => {
            const btn = container.querySelector('.lang-btn');
            const dropdown = container.querySelector('.lang-dropdown');

            if (!btn || !dropdown) return;

            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                const isOpen = container.classList.toggle('open');
                btn.setAttribute('aria-expanded', isOpen);
            });
        });

        // Close on outside click
        document.addEventListener('click', function (e) {
            switchers.forEach(container => {
                if (!container.contains(e.target)) {
                    container.classList.remove('open');
                    const btn = container.querySelector('.lang-btn');
                    if (btn) btn.setAttribute('aria-expanded', 'false');
                }
            });
        });

        // Close on Escape
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                switchers.forEach(container => {
                    container.classList.remove('open');
                    const btn = container.querySelector('.lang-btn');
                    if (btn) btn.setAttribute('aria-expanded', 'false');
                });
            }
        });
    }

    // ── Init on DOM ready ───────────────────────────
    document.addEventListener('DOMContentLoaded', function () {
        // Read current language from cookie (set by Django's set_language)
        const lang = getCookie('django_language') || document.documentElement.lang || 'en';
        applyDirection(lang);
        initSwitcher();
    });
})();
