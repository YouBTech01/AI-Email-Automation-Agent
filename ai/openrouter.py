"""
OpenRouter API Client: Dynamic Model Discovery, Completions, and Tool Calling.
"""
import json
import requests
from typing import Dict, Any, List, Optional
from database.database import log_activity

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

def fetch_openrouter_models(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch live list of all models available on OpenRouter."""
    headers = {
        "HTTP-Referer": "https://ai-email-agent.local",
        "X-Title": "AI Email Automation Agent"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = requests.get(OPENROUTER_MODELS_URL, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            models_raw = data.get('data', [])
            formatted = []
            for m in models_raw:
                pricing = m.get('pricing', {})
                prompt_price = float(pricing.get('prompt', 0)) * 1000000
                is_free = (prompt_price == 0)
                
                formatted.append({
                    'id': m.get('id'),
                    'name': m.get('name', m.get('id')),
                    'description': m.get('description', ''),
                    'context_length': m.get('context_length', 0),
                    'is_free': is_free,
                    'pricing_prompt_m': f"${prompt_price:.2f}/M tokens" if not is_free else "Free",
                    'pricing_tier': 'Free' if is_free else ('Very Low' if prompt_price < 0.5 else ('Low' if prompt_price < 2.0 else 'Standard')),
                    'architecture': m.get('architecture', {}),
                    'top_provider': m.get('top_provider', {})
                })
            return formatted
    except Exception as e:
        log_activity('AI', 'Failed to Fetch OpenRouter Models', actor='system', details={'error': str(e)}, status='WARNING')
    return []

def openrouter_chat_completion(
    messages: List[Dict[str, Any]],
    model: str,
    api_key: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    top_p: float = 1.0,
    timeout: int = 60
) -> Dict[str, Any]:
    """Execute chat completion with tool calling support via OpenRouter API."""
    if not api_key:
        return {'success': False, 'error': 'OpenRouter API key is not configured.'}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://ai-email-agent.local",
        "X-Title": "AI Email Automation Agent",
        "Content-Type": "application/json"
    }

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p
    }

    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        resp = requests.post(OPENROUTER_CHAT_URL, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            err_msg = f"OpenRouter HTTP {resp.status_code}: {resp.text}"
            try:
                err_json = resp.json()
                err_msg = err_json.get('error', {}).get('message', err_msg)
            except Exception:
                pass
            return {'success': False, 'error': err_msg, 'status_code': resp.status_code}

        data = resp.json()
        choice = data.get('choices', [{}])[0]
        message = choice.get('message', {})
        usage = data.get('usage', {})

        tool_calls = message.get('tool_calls', [])
        content = message.get('content', '')

        return {
            'success': True,
            'content': content,
            'tool_calls': tool_calls,
            'finish_reason': choice.get('finish_reason'),
            'usage': usage,
            'model': data.get('model', model),
            'provider': 'openrouter'
        }
    except requests.exceptions.Timeout:
        return {'success': False, 'error': f'Request timed out after {timeout} seconds.'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
