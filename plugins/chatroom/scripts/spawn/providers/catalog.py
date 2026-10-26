# Adattato da free-claude-code (Alishahryar1), AGPL-3.0-only, commit 707b6dd: src/free_claude_code/config/provider_catalog.py
# e src/free_claude_code/providers/credential_validation.py (le sonde di verifica delle chiavi)
"""The providers of the spawn mode: the ones with free models, in the order the "Prepara spawn" card lists them.

Each entry: name, base URL (OpenAI-compatible Chat Completions), where to sign up and create the key, the environment
variable that may hold a key, how the key travels (auth), extra fields the provider needs (Cloudflare: the account ID),
and the probe that checks a key without generating anything (verify: path or absolute URL, the field a good answer has,
the statuses that mean "rejected"); all_free: the free tier covers every model of the provider (its model list has
no prices), else a model is free when its own entry says so. A provider without a probe can only be "unverified": a public model list cannot tell
a good key from a bad one. Subscription providers (ChatGPT, Copilot, Kimi Code, coding plans) are left out on purpose."""

FREE = {
    'open_router': {'name': 'OpenRouter', 'base': 'https://openrouter.ai/api/v1', 'signup': 'https://openrouter.ai/keys',
                    'env': 'OPENROUTER_API_KEY', 'pkce': True, 'offer': '20 :free models',
                    'verify': ('/key', 'data', (401,))},
    'nvidia_nim': {'all_free': True, 'name': 'NVIDIA NIM', 'base': 'https://integrate.api.nvidia.com/v1', 'signup': 'https://build.nvidia.com/settings/api-keys',
                   'env': 'NVIDIA_NIM_API_KEY', 'offer': 'whole catalog, rate limited'},
    'groq': {'all_free': True, 'name': 'Groq', 'base': 'https://api.groq.com/openai/v1', 'signup': 'https://console.groq.com/keys',
             'env': 'GROQ_API_KEY', 'offer': 'free tier', 'verify': ('/models', 'data', (401,))},
    'gemini': {'all_free': True, 'name': 'Google AI Studio', 'base': 'https://generativelanguage.googleapis.com/v1beta/openai', 'signup': 'https://aistudio.google.com/apikey',
               'env': 'GEMINI_API_KEY', 'offer': 'free tier', 'auth': 'x-goog-api-key',
               'verify': ('https://generativelanguage.googleapis.com/v1beta/models?pageSize=1', 'models', ())},
    'mistral': {'all_free': True, 'name': 'Mistral La Plateforme', 'base': 'https://api.mistral.ai/v1', 'signup': 'https://console.mistral.ai/',
                'env': 'MISTRAL_API_KEY', 'offer': 'Experiment plan', 'verify': ('/models', 'data', ())},
    'mistral_codestral': {'all_free': True, 'name': 'Mistral Codestral', 'base': 'https://codestral.mistral.ai/v1', 'signup': 'https://console.mistral.ai/',
                          'env': 'CODESTRAL_API_KEY', 'offer': 'codestral, devstral'},
    'cerebras': {'all_free': True, 'name': 'Cerebras', 'base': 'https://api.cerebras.ai/v1', 'signup': 'https://cloud.cerebras.ai',
                 'env': 'CEREBRAS_API_KEY', 'offer': 'free tier', 'verify': ('/models', 'data', ())},
    'sambanova': {'all_free': True, 'name': 'SambaNova', 'base': 'https://api.sambanova.ai/v1', 'signup': 'https://cloud.sambanova.ai/apis',
                  'env': 'SAMBANOVA_API_KEY', 'offer': 'free tier', 'verify': ('/models', 'data', ())},
    'cohere': {'all_free': True, 'name': 'Cohere', 'base': 'https://api.cohere.ai/compatibility/v1', 'signup': 'https://dashboard.cohere.com/api-keys',
               'env': 'COHERE_API_KEY', 'offer': 'trial key', 'verify': ('https://api.cohere.com/v1/models?page_size=1', 'models', (401, 498))},
    'cloudflare': {'all_free': True, 'name': 'Cloudflare Workers AI', 'base': 'https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1',
                   'signup': 'https://dash.cloudflare.com/profile/api-tokens', 'env': 'CLOUDFLARE_API_TOKEN', 'offer': 'daily free neurons',
                   'extra': ('account_id',), 'verify': ('https://api.cloudflare.com/client/v4/accounts/{account_id}/tokens/verify', 'result', (401,)),
                   # an account token (the dashboard's default) is only known to its account's endpoint; a user token to /user
                   'verify_fallback': ('https://api.cloudflare.com/client/v4/user/tokens/verify', 'result', (401,))},
    'huggingface': {'all_free': True, 'name': 'Hugging Face', 'base': 'https://router.huggingface.co/v1', 'signup': 'https://huggingface.co/settings/tokens',
                    'env': 'HUGGINGFACE_API_KEY', 'offer': 'monthly credits', 'verify': ('https://huggingface.co/api/whoami-v2', 'name', (401,))},
    'siliconflow': {'name': 'SiliconFlow', 'base': 'https://api.siliconflow.com/v1', 'signup': 'https://cloud.siliconflow.com/account/ak',
                    'env': 'SILICONFLOW_API_KEY', 'offer': 'small models free', 'verify': ('/user/info', 'data', (401,))},
    'ollama_cloud': {'all_free': True, 'name': 'Ollama Cloud', 'base': 'https://ollama.com/v1', 'signup': 'https://ollama.com/settings/keys',
                     'env': 'OLLAMA_API_KEY', 'offer': 'free quota'},
    'kilo': {'name': 'Kilo', 'base': 'https://api.kilo.ai/api/gateway', 'signup': 'https://app.kilo.ai', 'env': 'KILO_API_KEY', 'offer': 'free models'},
    'opencode_zen': {'name': 'OpenCode Zen', 'base': 'https://opencode.ai/zen/v1', 'signup': 'https://opencode.ai/auth',
                     'env': 'OPENCODE_API_KEY', 'offer': 'free models'},
    'vercel': {'name': 'Vercel AI Gateway', 'base': 'https://ai-gateway.vercel.sh/v1', 'signup': 'https://vercel.com/docs/ai-gateway',
               'env': 'AI_GATEWAY_API_KEY', 'offer': 'credits and free models', 'verify': ('/credits', 'balance', (401,))},
    'zenmux': {'name': 'ZenMux', 'base': 'https://zenmux.ai/api/v1', 'signup': 'https://zenmux.ai/platform/pay-as-you-go',
               'env': 'ZENMUX_API_KEY', 'offer': '2 free models'},
    'orcarouter': {'name': 'OrcaRouter', 'base': 'https://api.orcarouter.ai/v1', 'signup': 'https://www.orcarouter.ai/console',
                   'env': 'ORCAROUTER_API_KEY', 'offer': '5 free models', 'verify': ('/models', 'data', (401,))},
    'tokenrouter': {'name': 'TokenRouter', 'base': 'https://api.tokenrouter.com/v1', 'signup': 'https://www.tokenrouter.com/',
                    'env': 'TOKENROUTER_API_KEY', 'offer': 'glm-5.3 free'},
    'nararoute': {'name': 'NaraRoute', 'base': 'https://router.bynara.id/v1', 'signup': 'https://router.bynara.id/keys',
                  'env': 'NARAROUTE_API_KEY', 'offer': 'free models', 'verify': ('/models', 'data', (401,))},
    'xkiro': {'name': 'xKiro', 'base': 'https://api.xkiro.com/v1', 'signup': 'https://xkiro.com/dashboard/api/keys',
              'env': 'XKIRO_API_KEY', 'offer': ':free models', 'verify': ('/usage', 'windows', (401,))},
    'llm7': {'all_free': True, 'name': 'LLM7', 'base': 'https://api.llm7.io/v1', 'signup': 'https://dash.llm7.io/', 'env': 'LLM7_API_KEY', 'offer': 'free'},
    'zai_api': {'name': 'Z.ai API', 'base': 'https://api.z.ai/api/paas/v4', 'signup': 'https://z.ai/manage-apikey/apikey-list',
                'env': 'ZAI_API_KEY', 'offer': 'glm flash free'},
    'agnes': {'name': 'Agnes AI', 'base': 'https://apihub.agnes-ai.com/v1', 'signup': 'https://agnes-ai.com/', 'env': 'AGNES_API_KEY',
              'offer': '3 flash models free'},
    'poolside': {'name': 'Poolside', 'base': 'https://inference.poolside.ai/v1', 'signup': 'https://platform.poolside.ai/',
                 'env': 'POOLSIDE_API_KEY', 'offer': 'laguna free'},
    'novita': {'name': 'Novita', 'base': 'https://api.novita.ai/openai/v1', 'signup': 'https://novita.ai/settings/key-management',
               'env': 'NOVITA_API_KEY', 'offer': '1 free model',
               'verify': ('https://api.novita.ai/openapi/v1/billing/balance/detail', 'availableBalance', ())},
}

# not a model provider: the benchmark data of the catalog (decision D2: free key, 100 requests a day), asked for in the
# same first setup. Its probe spends one of the 100 requests.
ARTIFICIAL_ANALYSIS = {'name': 'Artificial Analysis', 'base': 'https://artificialanalysis.ai/api/v2', 'signup': 'https://artificialanalysis.ai/',
                       'env': 'ARTIFICIAL_ANALYSIS_API_KEY', 'offer': 'benchmarks, 100 requests a day', 'auth': 'x-api-key',
                       'verify': ('/data/llms/models', 'data', (401, 403))}

ALL = {**FREE, 'artificial_analysis': ARTIFICIAL_ANALYSIS}


class UnknownProvider(ValueError, KeyError):
    """a ValueError for the viewer and the cards (they answer 400 with it), a KeyError for older callers"""

    def __str__(self):
        return str(self.args[0])


def get(provider):
    """the entry of one provider, or UnknownProvider naming the known ones"""
    try:
        return ALL[provider]
    except KeyError:
        raise UnknownProvider(f'unknown provider {str(provider)[:40]!r}; known: {", ".join(ALL)}') from None


def base_url(provider, extra=None):
    """the provider's base URL with its extra fields filled (Cloudflare's account ID)"""
    return get(provider)['base'].format(**(extra or {}))


def auth_headers(provider, key):
    """how the key travels: a bearer token, or the provider's own header"""
    how = get(provider).get('auth', 'bearer')
    return {'Authorization': f'Bearer {key}'} if how == 'bearer' else {how: key}
