"""
Multi-Provider Adapters for OpenAI-Compatible Endpoints (OpenAI, Groq, DeepSeek, Custom).
"""
import requests
from typing import Dict, Any, List, Optional

def generic_openai_chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    auth_header: str = 'Authorization',
    auth_prefix: str = 'Bearer ',
    temperature: float = 0.7,
    max_tokens: int = 2048,
    top_p: float = 1.0,
    timeout: int = 60
) -> Dict[str, Any]:
    """Execute chat completion against any standard OpenAI-compatible API endpoint."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers[auth_header] = f"{auth_prefix}{api_key}" if auth_prefix else api_key

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
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            err_msg = f"Provider HTTP {resp.status_code}: {resp.text}"
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

        return {
            'success': True,
            'content': message.get('content', ''),
            'tool_calls': message.get('tool_calls', []),
            'finish_reason': choice.get('finish_reason'),
            'usage': usage,
            'model': data.get('model', model),
            'provider': 'openai_compatible'
        }
    except requests.exceptions.Timeout:
        return {'success': False, 'error': f'Request timed out after {timeout} seconds.'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_provider_connection(base_url: str, api_key: str, model: str, provider_type: str = 'openrouter') -> Dict[str, Any]:
    """Send a lightweight ping to verify provider credentials and endpoint connectivity."""
    test_messages = [{"role": "user", "content": "Respond with the word 'OK' only."}]
    if provider_type == 'openrouter':
        from ai.openrouter import openrouter_chat_completion
        return openrouter_chat_completion(test_messages, model=model or 'openai/gpt-4o-mini', api_key=api_key, max_tokens=10, timeout=15)
    else:
        return generic_openai_chat_completion(base_url, api_key, model=model, messages=test_messages, max_tokens=10, timeout=15)
