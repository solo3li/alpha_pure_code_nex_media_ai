import glob
import re

html_files = glob.glob(r'd:\Projects\nexmedia\web_apps\**\*.html', recursive=True)

for file in html_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip if already injected
    if 'language_switcher.html' in content:
        print(f"Skipping {file}, already injected.")
        continue

    # 1. Add templatetags and get language
    if '{% load static %}' in content:
        content = content.replace('{% load static %}', '{% load static %}\n{% load i18n %}\n{% get_current_language as CURRENT_LANG %}')
    elif '<!DOCTYPE html>' in content:
        content = content.replace('<!DOCTYPE html>', '{% load i18n %}\n{% get_current_language as CURRENT_LANG %}\n<!DOCTYPE html>')
    
    # 2. Modify html tag
    match = re.search(r'<html([^>]*)>', content)
    if match:
        html_tag = match.group(0)
        if 'lang="' in html_tag:
            new_tag = re.sub(r'lang="[^"]*"', 'lang="{{ CURRENT_LANG }}" dir="{% if CURRENT_LANG == \'ar\' %}rtl{% else %}ltr{% endif %}"', html_tag)
        else:
            new_tag = html_tag.replace('<html', '<html lang="{{ CURRENT_LANG }}" dir="{% if CURRENT_LANG == \'ar\' %}rtl{% else %}ltr{% endif %}"')
        content = content.replace(html_tag, new_tag)

    # 3. Inject CSS before </head>
    css_inject = '''
  <!-- Language Switcher CSS -->
  <link rel="stylesheet" href="{% static \'home/css/lang-switcher.css\' %}">
  {% if CURRENT_LANG == \'ar\' %}
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800&family=Tajawal:wght@300;400;500;700&display=swap">
  {% endif %}
</head>'''
    content = content.replace('</head>', css_inject)

    # 4. Inject JS before </body>
    js_inject = '''
  <!-- Language Switcher JS -->
  <script src="{% static \'home/js/lang-switcher.js\' %}"></script>
</body>'''
    content = content.replace('</body>', js_inject)

    # 5. Inject Dropdown Widget
    # First, look for profile section inside nav
    if '<div class="profile-section">' in content:
        content = content.replace('<div class="profile-section">', '<div class="profile-section">\n        {% include "partials/language_switcher.html" %}')
    elif '<div class="nav-right">' in content:
        content = content.replace('<div class="nav-right">', '<div class="nav-right">\n        {% include "partials/language_switcher.html" %}')
    elif '<div class="nav-menu">' in content:
        content = content.replace('</div>\n      \n      <div class="user-profile">', '{% include "partials/language_switcher.html" %}\n      </div>\n      \n      <div class="user-profile">')
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Updated {file}")
