# core_apps/home/utils.py

TOOL_DISPLAY_NAMES = {
    "bg-remover": "Image Background remover",
    "text-to-cartoon": "Text to Cartoon",
    "make-my-trip": "Make my trip with AI",
    "text-to-voice": "Voice Generator",
    "video-caption": "Video caption Generator",
    "img-to-txt": "Image to text",
    "video-bg-remover": "Video Background remover",
    "voice-to-text": "Voice to text",
    "GPT-3.5": "GPT 3.5",
    "GPT-4o": "GPT 4o"
}

TOOL_UNITS = {
    "bg-remover": "photo",
    "text-to-cartoon": "prompt",
    "make-my-trip": "Trip",
    "text-to-voice": "character",
    "video-caption": "minutes",
    "img-to-txt": "image",
    "video-bg-remover": "seconds",
    "voice-to-text": "minutes",
    "GPT-3.5": "Words",
    "GPT-4o": "Words"
}

def get_tool_display_name(tool_name):
    return TOOL_DISPLAY_NAMES.get(tool_name, tool_name.replace("-", " "))

def get_tool_unit(tool_name):
    return TOOL_UNITS.get(tool_name, "")
