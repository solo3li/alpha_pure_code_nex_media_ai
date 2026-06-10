from core_apps.tools.models import Tool 

def get_tool_id(tool_name):
    """
    Get the tool ID for a given tool name
    """
    try:
        tool = Tool.objects.filter(name=tool_name).first()
        return tool.id if tool else None
    except Exception as e:
        print(f"Error getting tool ID: {str(e)}")
        return None