"""
AI Safety Engine: Risk Tiers, Permission Gates, and Confidence Evaluation.
"""
from typing import Dict, Any, Tuple
from auth.middleware import user_has_permission
from database.database import log_activity

TOOL_RISK_MAP = {
    "gmail_search": "LOW",
    "gmail_get_message": "LOW",
    "gmail_get_thread": "LOW",
    "contact_search": "LOW",
    "contact_list": "LOW",
    "automation_list": "LOW",
    "training_rule_list": "LOW",
    "training_knowledge_list": "LOW",
    "template_list": "LOW",
    "report_generate": "LOW",

    "gmail_create_draft": "MEDIUM",
    "gmail_update_draft": "MEDIUM",
    "gmail_delete_draft": "MEDIUM",
    "gmail_untrash": "MEDIUM",
    "contact_create": "MEDIUM",
    "contact_update": "MEDIUM",
    "automation_create": "MEDIUM",
    "automation_update": "MEDIUM",
    "automation_toggle": "MEDIUM",
    "training_rule_create": "MEDIUM",
    "training_rule_delete": "MEDIUM",
    "training_knowledge_create": "MEDIUM",
    "training_knowledge_delete": "MEDIUM",
    "template_create": "MEDIUM",
    "template_delete": "MEDIUM",
    "database_backup_create": "MEDIUM",
    "gmail_modify_labels": "MEDIUM",

    "gmail_send": "HIGH",
    "gmail_reply": "HIGH",
    "gmail_forward": "HIGH",
    "gmail_trash": "HIGH",
    "automation_delete": "HIGH",
    "contact_delete": "HIGH"
}

TOOL_PERMISSION_MAP = {
    "gmail_search": "view_emails",
    "gmail_get_message": "view_emails",
    "gmail_get_thread": "view_emails",
    "gmail_create_draft": "manage_drafts",
    "gmail_update_draft": "manage_drafts",
    "gmail_delete_draft": "manage_drafts",
    "gmail_send": "send_emails",
    "gmail_reply": "send_emails",
    "gmail_forward": "send_emails",
    "gmail_modify_labels": "modify_labels",
    "gmail_trash": "modify_labels",
    "gmail_untrash": "modify_labels",
    "contact_search": "view_emails",
    "contact_list": "view_emails",
    "contact_create": "view_emails",
    "contact_update": "view_emails",
    "contact_delete": "view_emails",
    "automation_list": "manage_automations",
    "automation_create": "manage_automations",
    "automation_update": "manage_automations",
    "automation_delete": "manage_automations",
    "automation_toggle": "manage_automations",
    "training_rule_list": "manage_ai_training",
    "training_rule_create": "manage_ai_training",
    "training_rule_delete": "manage_ai_training",
    "training_knowledge_list": "manage_ai_training",
    "training_knowledge_create": "manage_ai_training",
    "training_knowledge_delete": "manage_ai_training",
    "template_list": "manage_templates",
    "template_create": "manage_templates",
    "template_delete": "manage_templates",
    "database_backup_create": "manage_settings",
    "report_generate": "use_ai_chat"
}

def classify_tool_risk(tool_name: str) -> str:
    """Return risk classification tier: LOW, MEDIUM, or HIGH."""
    return TOOL_RISK_MAP.get(tool_name, "HIGH")

def validate_tool_execution(user_id: int, tool_name: str, tool_args: Dict[str, Any], is_automation: bool = False, approval_mode: str = 'draft_only') -> Tuple[bool, str, str]:
    """
    Validate if tool can be executed directly or requires confirmation.
    Returns: (is_allowed, risk_tier, reason)
    """
    risk = classify_tool_risk(tool_name)
    required_perm = TOOL_PERMISSION_MAP.get(tool_name)

    # 1. User permission check (if triggered by user in chat)
    if user_id and required_perm:
        if not user_has_permission(user_id, required_perm):
            log_activity('SECURITY', f"Permission Denied for Tool: {tool_name}", actor=f"user_{user_id}", status='BLOCKED')
            return False, risk, f"Missing required permission: {required_perm}"

    # 2. High-risk safety gate
    if risk == "HIGH":
        if is_automation:
            if approval_mode != 'trusted_auto':
                return False, risk, "Automation level requires admin confirmation for high-impact actions."
        else:
            # In chat, high-risk tools require explicit user confirmation card
            return False, risk, "High-impact action requires user confirmation."

    return True, risk, "OK"
