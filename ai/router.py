"""
AI Router & Fallback Orchestration Engine.
Handles primary model invocation, automatic fallback model retry, secondary provider switching, and error logging.
"""
from typing import Dict, Any, List, Optional
from database.database import query_db, log_activity
from database.crypto import decrypt_value
from ai.openrouter import openrouter_chat_completion
from ai.providers import generic_openai_chat_completion

def route_ai_request(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    preferred_provider_id: Optional[int] = None,
    preferred_model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> Dict[str, Any]:
    """
    Execute AI completion with automatic multi-level fallback chain:
    1. Primary Provider + Primary Model
    2. Primary Provider + Fallback Model
    3. Secondary Active Provider + Default Model
    """
    # 1. Fetch active providers
    if preferred_provider_id:
        primary_provider = query_db("SELECT * FROM ai_providers WHERE id = ? AND is_active = 1", (preferred_provider_id,), one=True)
    else:
        primary_provider = query_db("SELECT * FROM ai_providers WHERE is_primary = 1 AND is_active = 1", one=True)
        if not primary_provider:
            primary_provider = query_db("SELECT * FROM ai_providers WHERE is_active = 1 ORDER BY id ASC", one=True)

    if not primary_provider:
        return {'success': False, 'error': 'No active AI providers configured. Please configure OpenRouter or custom API in Settings.', 'category': 'AI_CONFIG_ERROR'}

    api_key = decrypt_value(primary_provider.get('api_key_enc', ''))
    target_model = preferred_model or primary_provider.get('default_model', 'openai/gpt-4o-mini')

    # STEP 1: Attempt Primary Provider + Target Model
    result = _call_provider(primary_provider, target_model, api_key, messages, tools, temperature, max_tokens)
    if result.get('success'):
        return result

    log_activity('AI', 'Primary Model Failed, Trying Fallback Model', actor='ai-router', 
                 details={'provider': primary_provider['name'], 'model': target_model, 'error': result.get('error')}, 
                 status='WARNING')

    # STEP 2: Attempt Fallback Model on Primary Provider
    fallback_model = primary_provider.get('fallback_model')
    if fallback_model and fallback_model != target_model:
        fallback_result = _call_provider(primary_provider, fallback_model, api_key, messages, tools, temperature, max_tokens)
        if fallback_result.get('success'):
            fallback_result['is_fallback'] = True
            fallback_result['fallback_reason'] = f"Primary model {target_model} failed: {result.get('error')}"
            return fallback_result

    # STEP 3: Attempt Secondary Active Provider
    secondary_providers = query_db(
        "SELECT * FROM ai_providers WHERE id != ? AND is_active = 1 ORDER BY is_primary DESC, id ASC", 
        (primary_provider['id'],)
    )
    for sec_p in secondary_providers:
        sec_api_key = decrypt_value(sec_p.get('api_key_enc', ''))
        sec_model = sec_p.get('default_model')
        sec_result = _call_provider(sec_p, sec_model, sec_api_key, messages, tools, temperature, max_tokens)
        if sec_result.get('success'):
            sec_result['is_fallback'] = True
            sec_result['fallback_reason'] = f"Switched to secondary provider {sec_p['name']} ({sec_model})"
            log_activity('AI', 'Secondary Provider Succeeded', actor='ai-router', details={'provider': sec_p['name']})
            return sec_result

    # All Providers and Models Failed
    error_msg = f"All AI providers and fallback models failed. Last error: {result.get('error')}"
    log_activity('AI', 'All AI Providers Failed', actor='ai-router', details={'error': error_msg}, status='FAILED')
    return {
        'success': False,
        'error': error_msg,
        'category': 'AI_ERROR',
        'raw_error': result.get('error')
    }

def _call_provider(provider: dict, model: str, api_key: str, messages: list, tools: Optional[list],
                   temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> dict:
    """Invoke specific provider adapter."""
    p_type = provider.get('provider_type', 'openrouter')
    base_url = provider.get('base_url', '')
    temp = temperature if temperature is not None else provider.get('temperature', 0.7)
    tokens = max_tokens if max_tokens is not None else provider.get('max_tokens', 2048)
    top_p = provider.get('top_p', 1.0)
    timeout = provider.get('timeout_seconds', 60)

    if p_type == 'openrouter':
        return openrouter_chat_completion(
            messages=messages,
            model=model,
            api_key=api_key,
            tools=tools,
            temperature=temp,
            max_tokens=tokens,
            top_p=top_p,
            timeout=timeout
        )
    else:
        return generic_openai_chat_completion(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=messages,
            tools=tools,
            auth_header=provider.get('auth_header', 'Authorization'),
            auth_prefix=provider.get('auth_prefix', 'Bearer '),
            temperature=temp,
            max_tokens=tokens,
            top_p=top_p,
            timeout=timeout
        )
