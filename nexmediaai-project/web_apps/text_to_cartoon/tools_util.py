# backend/utils/tool_utils.py
from core_apps.tools.models import Tool, ToolUsageHistory
from core_apps.tool_data.models import FileToolData
from django.db import transaction

def get_tool_id(tool_name):
    try:
        tool = Tool.objects.filter(name=tool_name).first()
        return tool.id if tool else None
    except Exception as e:
        print(f"Error getting tool ID: {e}")
        return None

def save_file_tool_data(file_name, file_path):
    try:
        file_tool_data = FileToolData(file_name=file_name, file_path=file_path)
        file_tool_data.save()
        return file_tool_data.id
    except Exception as e:
        print(f"Error saving file tool data: {e}")
        raise e

def save_tool_usage(user_id, tool_id, additional_data_id):
    try:
        usage = ToolUsageHistory(
            user_id=user_id,
            tool_id=tool_id,
            additional_data_id=additional_data_id
        )
        usage.save()
    except Exception as e:
        print(f"Error saving tool usage: {e}")
        raise e
