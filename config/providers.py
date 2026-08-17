"""
Preconfigured AI Provider Metadata, endpoints, and default models.
"""

SUPPORTED_PROVIDERS = {
    'openrouter': {
        'name': 'OpenRouter',
        'display_name': 'OpenRouter (Recommended)',
        'description': 'Access hundreds of AI models (OpenAI, Anthropic, Google, DeepSeek, Meta, Mistral, Groq) with a single API key.',
        'base_url': 'https://openrouter.ai/api/v1',
        'models_endpoint': 'https://openrouter.ai/api/v1/models',
        'auth_header': 'Authorization',
        'auth_prefix': 'Bearer ',
        'default_model': 'openai/gpt-4o-mini',
        'popular_models': [
            {'id': 'openai/gpt-4o-mini', 'name': 'GPT-4o Mini (Fast & Cheap)', 'context': 128000, 'pricing': 'Very Low'},
            {'id': 'openai/gpt-4o', 'name': 'GPT-4o (High Intelligence)', 'context': 128000, 'pricing': 'Medium'},
            {'id': 'anthropic/claude-3.5-sonnet', 'name': 'Claude 3.5 Sonnet (State of the Art)', 'context': 200000, 'pricing': 'Medium'},
            {'id': 'google/gemini-2.0-flash-exp:free', 'name': 'Gemini 2.0 Flash (Free / High Speed)', 'context': 1000000, 'pricing': 'Free'},
            {'id': 'google/gemini-pro-1.5', 'name': 'Gemini 1.5 Pro', 'context': 2000000, 'pricing': 'Medium'},
            {'id': 'deepseek/deepseek-chat', 'name': 'DeepSeek V3 (Affordable & Powerful)', 'context': 64000, 'pricing': 'Very Low'},
            {'id': 'meta-llama/llama-3.3-70b-instruct', 'name': 'Llama 3.3 70B Instruct', 'context': 128000, 'pricing': 'Low'},
            {'id': 'mistralai/mistral-large-2411', 'name': 'Mistral Large 2', 'context': 128000, 'pricing': 'Medium'},
            {'id': 'groq/llama-3.1-70b-versatile', 'name': 'Groq Llama 3.1 70B (Ultra Fast)', 'context': 128000, 'pricing': 'Low'}
        ]
    },
    'openai': {
        'name': 'OpenAI Direct',
        'display_name': 'OpenAI Direct API',
        'description': 'Direct connection to OpenAI API endpoint.',
        'base_url': 'https://api.openai.com/v1',
        'models_endpoint': 'https://api.openai.com/v1/models',
        'auth_header': 'Authorization',
        'auth_prefix': 'Bearer ',
        'default_model': 'gpt-4o-mini',
        'popular_models': [
            {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini', 'context': 128000, 'pricing': 'Low'},
            {'id': 'gpt-4o', 'name': 'GPT-4o', 'context': 128000, 'pricing': 'Medium'},
            {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo', 'context': 128000, 'pricing': 'High'}
        ]
    },
    'groq': {
        'name': 'Groq Cloud',
        'display_name': 'Groq Cloud (LPU Ultra-Fast)',
        'description': 'Ultra-fast inference using Groq LPU hardware.',
        'base_url': 'https://api.groq.com/openai/v1',
        'models_endpoint': 'https://api.groq.com/openai/v1/models',
        'auth_header': 'Authorization',
        'auth_prefix': 'Bearer ',
        'default_model': 'llama-3.3-70b-versatile',
        'popular_models': [
            {'id': 'llama-3.3-70b-versatile', 'name': 'Llama 3.3 70B Versatile', 'context': 128000, 'pricing': 'Low'},
            {'id': 'llama-3.1-8b-instant', 'name': 'Llama 3.1 8B Instant', 'context': 128000, 'pricing': 'Very Low'},
            {'id': 'mixtral-8x7b-32768', 'name': 'Mixtral 8x7B', 'context': 32768, 'pricing': 'Low'}
        ]
    },
    'deepseek': {
        'name': 'DeepSeek Direct',
        'display_name': 'DeepSeek API',
        'description': 'Direct connection to DeepSeek AI API.',
        'base_url': 'https://api.deepseek.com/v1',
        'models_endpoint': 'https://api.deepseek.com/v1/models',
        'auth_header': 'Authorization',
        'auth_prefix': 'Bearer ',
        'default_model': 'deepseek-chat',
        'popular_models': [
            {'id': 'deepseek-chat', 'name': 'DeepSeek-V3 Chat', 'context': 64000, 'pricing': 'Very Low'},
            {'id': 'deepseek-reasoner', 'name': 'DeepSeek-R1 Reasoner', 'context': 64000, 'pricing': 'Low'}
        ]
    },
    'custom': {
        'name': 'Custom OpenAI-Compatible',
        'display_name': 'Custom OpenAI-Compatible Provider',
        'description': 'Connect any custom OpenAI-compatible server (Local Ollama, vLLM, LM Studio, or Private API).',
        'base_url': 'http://localhost:11434/v1',
        'models_endpoint': '',
        'auth_header': 'Authorization',
        'auth_prefix': 'Bearer ',
        'default_model': 'custom-model',
        'popular_models': []
    }
}
