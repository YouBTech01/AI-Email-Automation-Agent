"""
AI Tool Registry, Function Schemas, and Safe Execution Router.
"""
import json
from datetime import datetime
from typing import Dict, Any, List
from gmail import messages as gmail_msg, threads as gmail_thr, actions as gmail_act
from database.database import query_db, insert_db, execute_db, log_activity

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "gmail_search",
            "description": "Search Gmail messages matching a specific search query (e.g. 'is:unread', 'from:john', 'subject:invoice', 'newer_than:2d').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string using Gmail search syntax."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of messages to retrieve (default: 10, max: 50).",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_get_message",
            "description": "Retrieve full details, body, headers, and attachments for a specific Gmail message by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The Gmail message ID."
                    }
                },
                "required": ["message_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_get_thread",
            "description": "Retrieve all messages and full conversation history for a specific Gmail thread.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thread_id": {
                        "type": "string",
                        "description": "The Gmail thread ID."
                    }
                },
                "required": ["thread_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_create_draft",
            "description": "Create a new Gmail draft without sending it. This is safe and allows the user to review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address."
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line."
                    },
                    "body_text": {
                        "type": "string",
                        "description": "Plain text email body content."
                    },
                    "body_html": {
                        "type": "string",
                        "description": "Optional HTML formatted email body content."
                    },
                    "thread_id": {
                        "type": "string",
                        "description": "Optional thread ID to reply to an existing thread."
                    }
                },
                "required": ["to", "subject", "body_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_update_draft",
            "description": "Update an existing draft's recipient, subject, or body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "The ID of the draft to update."
                    },
                    "to": {
                        "type": "string",
                        "description": "Recipient email address."
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line."
                    },
                    "body_text": {
                        "type": "string",
                        "description": "New plain text body content."
                    }
                },
                "required": ["draft_id", "to", "subject", "body_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_send",
            "description": "Send an email message immediately via Gmail API. HIGH RISK: Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address."
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line."
                    },
                    "body_text": {
                        "type": "string",
                        "description": "Plain text email body content."
                    },
                    "body_html": {
                        "type": "string",
                        "description": "Optional HTML formatted email body."
                    },
                    "thread_id": {
                        "type": "string",
                        "description": "Optional thread ID if sending within an existing thread."
                    }
                },
                "required": ["to", "subject", "body_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_reply",
            "description": "Reply directly to an existing email message. HIGH RISK: Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The ID of the message being replied to."
                    },
                    "reply_text": {
                        "type": "string",
                        "description": "The body of the reply message."
                    }
                },
                "required": ["message_id", "reply_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_forward",
            "description": "Forward an existing email to a new recipient with an optional note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The ID of the message to forward."
                    },
                    "to": {
                        "type": "string",
                        "description": "Recipient email address."
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional note to prepend to the forwarded email."
                    }
                },
                "required": ["message_id", "to"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_modify_labels",
            "description": "Add or remove labels from a message (e.g. mark read, archive, apply custom label).",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The Gmail message ID."
                    },
                    "add_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of label IDs or names to add (e.g. ['STARRED', 'IMPORTANT'])."
                    },
                    "remove_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of label IDs to remove (e.g. ['UNREAD', 'INBOX'])."
                    }
                },
                "required": ["message_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_trash",
            "description": "Move a message to Gmail Trash. HIGH RISK: Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The ID of the message to trash."
                    }
                },
                "required": ["message_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "contact_search",
            "description": "Search the local contacts directory for a person, email, or company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keyword for contact name, email, or company."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "contact_create",
            "description": "Add a new contact to the local address book.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name of the contact."},
                    "email": {"type": "string", "description": "Email address."},
                    "company": {"type": "string", "description": "Company name."},
                    "notes": {"type": "string", "description": "Optional notes or tags."}
                },
                "required": ["name", "email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "automation_create",
            "description": "Create and save a new automated workflow directly from user problem description or specifications. The workflow will be saved in the Automations section and immediately active.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Short, clear title for this automation (e.g. 'Customer Pricing Inquiries Reply')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed explanation of what this automation does."
                    },
                    "trigger_type": {
                        "type": "string",
                        "enum": ["new_email", "unread_email", "sender_match", "keyword_match", "has_attachment"],
                        "description": "The trigger event type."
                    },
                    "trigger_config": {
                        "type": "object",
                        "description": "Optional trigger parameters like keywords or sender."
                    },
                    "conditions": {
                        "type": "array",
                        "description": "List of condition rules to evaluate.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string", "enum": ["sender", "subject", "body", "ai_category", "has_attachment"]},
                                "operator": {"type": "string", "enum": ["contains", "not_contains", "equals", "not_equals", "matches_regex"]},
                                "value": {"type": "string"}
                            },
                            "required": ["field", "operator", "value"]
                        }
                    },
                    "actions": {
                        "type": "array",
                        "description": "List of actions to execute.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action_type": {"type": "string", "enum": ["generate_draft", "send_reply", "add_label", "archive", "forward"]},
                                "config": {
                                    "type": "object",
                                    "description": "Action config like instruction, label name, or forward email address."
                                }
                            },
                            "required": ["action_type"]
                        }
                    },
                    "approval_mode": {
                        "type": "string",
                        "enum": ["draft_only", "approval_required", "trusted_auto"],
                        "description": "Safety level: draft_only (Level 1), approval_required (Level 2), or trusted_auto (Level 3)."
                    },
                    "confidence_threshold": {
                        "type": "integer",
                        "description": "Confidence threshold percentage (default: 85)."
                    }
                },
                "required": ["name", "trigger_type", "actions"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_delete_draft",
            "description": "Delete a Gmail draft by its draft ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "The ID of the draft to delete."}
                },
                "required": ["draft_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_untrash",
            "description": "Restore a Gmail message from the Trash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "The ID of the message to restore."}
                },
                "required": ["message_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "automation_list",
            "description": "List all existing automated workflows and their current statuses.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "automation_update",
            "description": "Update or edit an existing automation workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "automation_id": {"type": "integer", "description": "ID of the automation to edit."},
                    "name": {"type": "string", "description": "Updated title."},
                    "description": {"type": "string", "description": "Updated description."},
                    "status": {"type": "string", "enum": ["ACTIVE", "PAUSED"]},
                    "approval_mode": {"type": "string", "enum": ["draft_only", "approval_required", "trusted_auto"]},
                    "confidence_threshold": {"type": "integer"}
                },
                "required": ["automation_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "automation_delete",
            "description": "Delete an automation workflow completely.",
            "parameters": {
                "type": "object",
                "properties": {
                    "automation_id": {"type": "integer", "description": "ID of the automation to delete."}
                },
                "required": ["automation_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "automation_toggle",
            "description": "Enable or pause a specific automation workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "automation_id": {"type": "integer", "description": "ID of the automation."},
                    "status": {"type": "string", "enum": ["ACTIVE", "PAUSED"], "description": "Desired status."}
                },
                "required": ["automation_id", "status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "training_rule_list",
            "description": "List all AI behavioral rules and constraints.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "training_rule_create",
            "description": "Add a new AI behavioral rule, tone guideline, or constraint.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_type": {"type": "string", "enum": ["tone", "constraint", "format", "custom"], "description": "Category of rule."},
                    "title": {"type": "string", "description": "Short rule title."},
                    "content": {"type": "string", "description": "Detailed rule instruction or constraint."},
                    "priority": {"type": "integer", "description": "Priority number (default 10)."}
                },
                "required": ["rule_type", "title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "training_rule_delete",
            "description": "Delete an AI behavioral rule by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "integer", "description": "Rule ID to delete."}
                },
                "required": ["rule_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "training_knowledge_list",
            "description": "List all company knowledge base articles and policies.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "training_knowledge_create",
            "description": "Add a new knowledge base article, FAQ, or policy item for the AI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "e.g. pricing, policy, support, product"},
                    "title": {"type": "string", "description": "Article title."},
                    "content": {"type": "string", "description": "Information or policy content."}
                },
                "required": ["category", "title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "training_knowledge_delete",
            "description": "Delete a knowledge base article by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge_id": {"type": "integer", "description": "Article ID to delete."}
                },
                "required": ["knowledge_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "template_list",
            "description": "List all reusable email templates.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "template_create",
            "description": "Create a new reusable email template.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Template name."},
                    "category": {"type": "string", "description": "Category (support, sales, general)."},
                    "subject": {"type": "string", "description": "Default subject line."},
                    "body_text": {"type": "string", "description": "Email body content with {{placeholders}}."}
                },
                "required": ["name", "subject", "body_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "template_delete",
            "description": "Delete an email template by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_id": {"type": "integer", "description": "Template ID to delete."}
                },
                "required": ["template_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "contact_list",
            "description": "List all contacts in the address book.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "contact_update",
            "description": "Edit or update an existing contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "integer", "description": "Contact ID."},
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "company": {"type": "string"},
                    "notes": {"type": "string"}
                },
                "required": ["contact_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "contact_delete",
            "description": "Delete a contact from the address book.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "integer", "description": "Contact ID to delete."}
                },
                "required": ["contact_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "database_backup_create",
            "description": "Create an immediate snapshot backup of the database.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "report_generate",
            "description": "Generate an executive intelligence summary report of recent emails and priorities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "enum": ["daily_summary", "weekly_summary", "security_audit"],
                        "description": "Type of report to generate."
                    }
                },
                "required": ["report_type"]
            }
        }
    }
]

def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a validated tool against backend services."""
    try:
        if tool_name == "gmail_search":
            query = tool_args.get("query", "")
            max_results = tool_args.get("max_results", 10)
            res = gmail_msg.search_messages(query=query, max_results=max_results)
            return res

        elif tool_name == "gmail_get_message":
            msg_id = tool_args.get("message_id")
            return gmail_msg.get_message(msg_id)

        elif tool_name == "gmail_get_thread":
            thread_id = tool_args.get("thread_id")
            return gmail_thr.get_thread(thread_id)

        elif tool_name == "gmail_create_draft":
            to = tool_args.get("to")
            subject = tool_args.get("subject")
            body_text = tool_args.get("body_text", "")
            body_html = tool_args.get("body_html", "")
            thread_id = tool_args.get("thread_id")
            return gmail_msg.create_draft(to=to, subject=subject, body_text=body_text, body_html=body_html, thread_id=thread_id)

        elif tool_name == "gmail_update_draft":
            draft_id = tool_args.get("draft_id")
            to = tool_args.get("to")
            subject = tool_args.get("subject")
            body_text = tool_args.get("body_text", "")
            return gmail_msg.update_draft(draft_id=draft_id, to=to, subject=subject, body_text=body_text)

        elif tool_name == "gmail_send":
            to = tool_args.get("to")
            subject = tool_args.get("subject")
            body_text = tool_args.get("body_text", "")
            body_html = tool_args.get("body_html", "")
            thread_id = tool_args.get("thread_id")
            return gmail_msg.send_message(to=to, subject=subject, body_text=body_text, body_html=body_html, thread_id=thread_id)

        elif tool_name == "gmail_reply":
            msg_id = tool_args.get("message_id")
            reply_text = tool_args.get("reply_text")
            orig = gmail_msg.get_message(msg_id)
            if not orig.get("success"):
                return orig
            msg_info = orig["message"]
            
            subject = msg_info.get("subject", "")
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"
            to = msg_info.get("from", "")
            thread_id = msg_info.get("threadId")
            in_reply_to = msg_info.get("message_id_header")
            references = msg_info.get("references") or in_reply_to

            return gmail_msg.send_message(
                to=to,
                subject=subject,
                body_text=reply_text,
                thread_id=thread_id,
                in_reply_to=in_reply_to,
                references=references
            )

        elif tool_name == "gmail_forward":
            msg_id = tool_args.get("message_id")
            to = tool_args.get("to")
            note = tool_args.get("note", "")
            orig = gmail_msg.get_message(msg_id)
            if not orig.get("success"):
                return orig
            msg_info = orig["message"]

            subject = msg_info.get("subject", "")
            if not subject.lower().startswith("fwd:"):
                subject = f"Fwd: {subject}"
            
            body = f"{note}\n\n---------- Forwarded message ---------\nFrom: {msg_info.get('from')}\nDate: {msg_info.get('date')}\nSubject: {msg_info.get('subject')}\nTo: {msg_info.get('to')}\n\n{msg_info.get('body_text')}"

            return gmail_msg.send_message(to=to, subject=subject, body_text=body)

        elif tool_name == "gmail_modify_labels":
            msg_id = tool_args.get("message_id")
            add_labels = tool_args.get("add_labels")
            remove_labels = tool_args.get("remove_labels")
            return gmail_act.modify_labels(msg_id, add_labels=add_labels, remove_labels=remove_labels)

        elif tool_name == "gmail_trash":
            msg_id = tool_args.get("message_id")
            return gmail_act.trash_message(msg_id)

        elif tool_name == "contact_search":
            query = tool_args.get("query", "")
            contacts = query_db(
                "SELECT * FROM contacts WHERE name LIKE ? OR email LIKE ? OR company LIKE ? LIMIT 10",
                (f"%{query}%", f"%{query}%", f"%{query}%")
            )
            return {'success': True, 'contacts': contacts}

        elif tool_name == "contact_create":
            name = tool_args.get("name")
            email = tool_args.get("email")
            company = tool_args.get("company", "")
            notes = tool_args.get("notes", "")
            c_id = insert_db(
                "INSERT INTO contacts (name, email, company, notes) VALUES (?, ?, ?, ?)",
                (name, email, company, notes)
            )
            return {'success': True, 'contact_id': c_id}

        elif tool_name == "automation_create":
            name = tool_args.get("name", "AI Assistant Workflow").strip()
            desc = tool_args.get("description", "").strip()
            trigger_type = tool_args.get("trigger_type", "new_email")
            approval_mode = tool_args.get("approval_mode", "draft_only")
            confidence = int(tool_args.get("confidence_threshold", 85))

            auto_id = insert_db(
                """INSERT INTO automations 
                   (name, description, status, trigger_type, confidence_threshold, approval_mode)
                   VALUES (?, ?, 'ACTIVE', ?, ?, ?)""",
                (name, desc, trigger_type, confidence, approval_mode)
            )

            # Insert trigger
            trig_cfg = json.dumps(tool_args.get("trigger_config", {}))
            insert_db("INSERT INTO automation_triggers (automation_id, trigger_type, config_json) VALUES (?, ?, ?)",
                      (auto_id, trigger_type, trig_cfg))

            # Insert conditions
            for c in tool_args.get("conditions", []):
                field = c.get("field", "sender")
                op = c.get("operator", "contains")
                val = c.get("value", "")
                is_ai = 1 if field.startswith("ai_") else 0
                insert_db("INSERT INTO automation_conditions (automation_id, field, operator, value, is_ai_condition) VALUES (?, ?, ?, ?, ?)",
                          (auto_id, field, op, val, is_ai))

            # Insert actions
            for idx, a in enumerate(tool_args.get("actions", [])):
                a_type = a.get("action_type", "generate_draft")
                a_cfg = json.dumps(a.get("config", {}))
                insert_db("INSERT INTO automation_actions (automation_id, action_type, config_json, sequence_order) VALUES (?, ?, ?, ?)",
                          (auto_id, a_type, a_cfg, idx + 1))

            log_activity('AUTOMATION', f"AI Created Automation '{name}'", actor='ai-agent', details={'id': auto_id})
            return {
                'success': True,
                'automation_id': auto_id,
                'name': name,
                'trigger_type': trigger_type,
                'approval_mode': approval_mode,
                'confidence_threshold': confidence,
                'view_url': f'/automations/builder/{auto_id}',
                'message': f"Automation '{name}' has been created and is active in your Automations section."
            }

        elif tool_name == "automation_list":
            automations = query_db("SELECT id, name, description, status, trigger_type, confidence_threshold, approval_mode FROM automations")
            return {'success': True, 'automations': automations}

        elif tool_name == "automation_toggle":
            auto_id = tool_args.get("automation_id")
            status = tool_args.get("status")
            execute_db("UPDATE automations SET status = ?, updated_at = ? WHERE id = ?", (status, datetime.utcnow().isoformat(), auto_id))
            return {'success': True, 'automation_id': auto_id, 'status': status}

        elif tool_name == "gmail_delete_draft":
            draft_id = tool_args.get("draft_id")
            return gmail_msg.delete_draft(draft_id)

        elif tool_name == "gmail_untrash":
            msg_id = tool_args.get("message_id")
            return gmail_act.untrash_message(msg_id)

        elif tool_name == "automation_update":
            auto_id = tool_args.get("automation_id")
            name = tool_args.get("name")
            desc = tool_args.get("description")
            status = tool_args.get("status")
            app_mode = tool_args.get("approval_mode")
            conf = tool_args.get("confidence_threshold")

            updates = []
            params = []
            if name:
                updates.append("name = ?"); params.append(name)
            if desc is not None:
                updates.append("description = ?"); params.append(desc)
            if status:
                updates.append("status = ?"); params.append(status)
            if app_mode:
                updates.append("approval_mode = ?"); params.append(app_mode)
            if conf is not None:
                updates.append("confidence_threshold = ?"); params.append(conf)

            if updates:
                updates.append("updated_at = ?")
                params.append(datetime.utcnow().isoformat())
                params.append(auto_id)
                execute_db(f"UPDATE automations SET {', '.join(updates)} WHERE id = ?", tuple(params))
            return {'success': True, 'automation_id': auto_id, 'message': 'Automation updated successfully.'}

        elif tool_name == "automation_delete":
            auto_id = tool_args.get("automation_id")
            execute_db("DELETE FROM automations WHERE id = ?", (auto_id,))
            return {'success': True, 'automation_id': auto_id, 'message': 'Automation deleted successfully.'}

        elif tool_name == "training_rule_list":
            rules = query_db("SELECT id, rule_type, title, content, is_active, priority FROM ai_training_rules ORDER BY priority ASC")
            return {'success': True, 'rules': rules}

        elif tool_name == "training_rule_create":
            r_type = tool_args.get("rule_type", "custom")
            title = tool_args.get("title")
            content = tool_args.get("content")
            prio = int(tool_args.get("priority", 10))
            r_id = insert_db("INSERT INTO ai_training_rules (rule_type, title, content, priority, is_active) VALUES (?, ?, ?, ?, 1)",
                             (r_type, title, content, prio))
            return {'success': True, 'rule_id': r_id, 'message': f"Training rule '{title}' created."}

        elif tool_name == "training_rule_delete":
            r_id = tool_args.get("rule_id")
            execute_db("DELETE FROM ai_training_rules WHERE id = ?", (r_id,))
            return {'success': True, 'rule_id': r_id, 'message': 'Rule deleted successfully.'}

        elif tool_name == "training_knowledge_list":
            items = query_db("SELECT id, category, title, content, is_active FROM ai_knowledge")
            return {'success': True, 'knowledge': items}

        elif tool_name == "training_knowledge_create":
            cat = tool_args.get("category", "general")
            title = tool_args.get("title")
            content = tool_args.get("content")
            k_id = insert_db("INSERT INTO ai_knowledge (category, title, content, is_active) VALUES (?, ?, ?, 1)",
                             (cat, title, content))
            return {'success': True, 'knowledge_id': k_id, 'message': f"Knowledge article '{title}' added."}

        elif tool_name == "training_knowledge_delete":
            k_id = tool_args.get("knowledge_id")
            execute_db("DELETE FROM ai_knowledge WHERE id = ?", (k_id,))
            return {'success': True, 'knowledge_id': k_id, 'message': 'Knowledge article deleted.'}

        elif tool_name == "template_list":
            templates = query_db("SELECT id, name, category, subject, body_text FROM email_templates")
            return {'success': True, 'templates': templates}

        elif tool_name == "template_create":
            name = tool_args.get("name")
            cat = tool_args.get("category", "General")
            subj = tool_args.get("subject")
            body = tool_args.get("body_text")
            t_id = insert_db("INSERT INTO email_templates (name, category, subject, body_text) VALUES (?, ?, ?, ?)",
                             (name, cat, subj, body))
            return {'success': True, 'template_id': t_id, 'message': f"Template '{name}' created."}

        elif tool_name == "template_delete":
            t_id = tool_args.get("template_id")
            execute_db("DELETE FROM email_templates WHERE id = ?", (t_id,))
            return {'success': True, 'template_id': t_id, 'message': 'Template deleted successfully.'}

        elif tool_name == "contact_list":
            contacts = query_db("SELECT id, name, email, company, notes FROM contacts ORDER BY name ASC")
            return {'success': True, 'contacts': contacts}

        elif tool_name == "contact_update":
            c_id = tool_args.get("contact_id")
            name = tool_args.get("name")
            email = tool_args.get("email")
            comp = tool_args.get("company")
            notes = tool_args.get("notes")
            updates = []; params = []
            if name: updates.append("name = ?"); params.append(name)
            if email: updates.append("email = ?"); params.append(email)
            if comp is not None: updates.append("company = ?"); params.append(comp)
            if notes is not None: updates.append("notes = ?"); params.append(notes)
            if updates:
                params.append(c_id)
                execute_db(f"UPDATE contacts SET {', '.join(updates)} WHERE id = ?", tuple(params))
            return {'success': True, 'contact_id': c_id, 'message': 'Contact updated.'}

        elif tool_name == "contact_delete":
            c_id = tool_args.get("contact_id")
            execute_db("DELETE FROM contacts WHERE id = ?", (c_id,))
            return {'success': True, 'contact_id': c_id, 'message': 'Contact deleted successfully.'}

        elif tool_name == "database_backup_create":
            from database.database import backup_db
            path = backup_db()
            return {'success': True, 'backup_path': path, 'message': 'Database snapshot created successfully.'}

        elif tool_name == "report_generate":
            from reports.service import generate_daily_report
            res = generate_daily_report()
            return {'success': True, 'report': res}

        else:
            return {'success': False, 'error': f"Unknown tool: {tool_name}"}

    except Exception as e:
        log_activity('AI', f"Tool Execution Failed: {tool_name}", actor='ai-agent', details={'error': str(e)}, status='FAILED')
        return {'success': False, 'error': str(e)}
