#!/usr/bin/env python
"""
Data loader script for Darijat TTS models.

Usage (on server):
    python manage.py shell < scripts/load_darijat_data.py

Or run it directly after setting DJANGO_SETTINGS_MODULE:
    DJANGO_SETTINGS_MODULE=config.settings.production python scripts/load_darijat_data.py
"""
import os
import sys
import json
import django

# ── Bootstrap Django ─────────────────────────────────────────────────────────
# Adjust the path so this script works when run from the project root.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.local'

django.setup()

# ── Imports after Django setup ───────────────────────────────────────────────
from web_apps.text_to_voice.models import (
    DarijatVoice,
    DarijatDialect,
    DarijatEmotion,
    DarijatStyle,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)


def load_json(filename):
    """Load a JSON file from the project root."""
    filepath = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(filepath):
        print(f"[WARN] File not found: {filepath}")
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_voices():
    """Load voices from voices.json. First 5 are free."""
    data = load_json('voices.json')
    if not data:
        return

    created = 0
    updated = 0
    GENDER_MAP = {
        'ذكر': 'male',
        'انثى': 'female',
        'أطفال': 'children',
    }

    for i, entry in enumerate(data):
        gender = GENDER_MAP.get(entry.get('gender', ''), 'male')
        is_premium = i >= 5  # First 5 voices are free

        obj, was_created = DarijatVoice.objects.update_or_create(
            name=entry['name'],
            defaults={
                'voice_name': entry['name'],  # Darijat API uses name as voice_name
                'accent': entry.get('accent', ''),
                'gender': gender,
                'is_premium': is_premium,
                'is_active': True,
                'order': i,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    print(f"[Voices]  Created: {created}, Updated: {updated}, Total: {len(data)}")


def load_dialects():
    """Load dialects from dialect.json."""
    data = load_json('dialect.json')
    if not data:
        return

    created = 0
    updated = 0

    for i, entry in enumerate(data):
        obj, was_created = DarijatDialect.objects.update_or_create(
            name=entry['name'],
            defaults={
                'value': entry['value'],
                'is_premium': False,
                'is_active': True,
                'order': i,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    print(f"[Dialects] Created: {created}, Updated: {updated}, Total: {len(data)}")


def load_emotions():
    """Load emotions from emotions.json."""
    data = load_json('emotions.json')
    if not data:
        return

    created = 0
    updated = 0

    for i, entry in enumerate(data):
        obj, was_created = DarijatEmotion.objects.update_or_create(
            name=entry['name'],
            defaults={
                'value': entry['value'],
                'is_premium': False,
                'is_active': True,
                'order': i,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    print(f"[Emotions] Created: {created}, Updated: {updated}, Total: {len(data)}")


def load_styles():
    """Load performance styles from styles.json."""
    data = load_json('styles.json')
    if not data:
        return

    created = 0
    updated = 0

    for i, entry in enumerate(data):
        obj, was_created = DarijatStyle.objects.update_or_create(
            name=entry['name'].strip(),
            defaults={
                'value': entry['value'].strip(),
                'is_premium': False,
                'is_active': True,
                'order': i,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    print(f"[Styles]  Created: {created}, Updated: {updated}, Total: {len(data)}")


def main():
    print("=" * 60)
    print("Loading Darijat TTS data into database...")
    print("=" * 60)

    load_voices()
    load_dialects()
    load_emotions()
    load_styles()

    print("=" * 60)
    print("Done! You can now manage these in Django Admin.")
    print("=" * 60)


if __name__ == '__main__':
    main()
