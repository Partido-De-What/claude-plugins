"""Identità comune dei modelli: lo stesso modello visto da più provider diventa una scheda sola con più strade.

Ogni provider scrive l'id a modo suo: `nvidia/nemotron-3-ultra-550b-a55b:free` (OpenRouter),
`nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B` (W&B), `zai-org/GLM-5.3` (SiliconFlow), `zai-glm-5-3` (Mistral),
`claude-opus-4-5@20251101` (Vertex), `Qwen/Qwen3.6-27B-TEE` (Chutes). canonical_id() li porta a una chiave sola:
il nome base senza organizzazione, in minuscolo, con i separatori uniformi e senza i suffissi che dicono solo come il
provider lo serve. Una chiave sbagliata che unisce due modelli diversi è peggio di due schede per lo stesso modello:
per questo si tolgono solo suffissi di servizio noti, mai parole come -turbo, -instruct o -latest."""
import re

SERVING_SUFFIXES = ('-free', '-tee', '-maas', '-fp8')    # come il provider serve il modello, non quale modello è
VENDOR_WORDS = ('nvidia', 'zai', 'z-ai', 'zai-org')       # vendor ripetuto in testa al nome (W&B, Mistral)


def canonical_id(model_id):
    """la chiave comune di un id di provider; '' per un id vuoto"""
    raw = str(model_id or '').strip().lower().lstrip('~')
    base = raw.rpartition('/')[2]
    base = base.split('@')[0].split(':')[0]               # @data (Vertex), :free :batch :provider (OpenRouter, Hugging Face)
    base = re.sub(r'[._\s]+', '-', base).strip('-')
    for suffix in SERVING_SUFFIXES:
        if base.endswith(suffix):
            base = base[:-len(suffix)]
    for word in VENDOR_WORDS:                             # solo vendor noti: "qwen/qwen-plus" resta qwen-plus
        if base.startswith(word + '-') and len(base) > len(word) + 1:
            base = base[len(word) + 1:]
            break
    return base


def merge(records):
    """{canonical: [record, ...]} dai record della scoperta ({'adapter', 'model_id', ...}), nell'ordine in cui arrivano"""
    out = {}
    for r in records:
        key = canonical_id(r.get('model_id'))
        if key:
            out.setdefault(key, []).append(r)
    return out


def _prova():
    same = [  # id veri da docs/adapter-modelli.md: ogni riga è un modello solo
        ('nvidia/nemotron-3-ultra-550b-a55b:free', 'nvidia/nemotron-3-ultra-550b-a55b', 'nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B',
         'nvidia/Nemotron-3-Ultra-550b-a55b'),
        ('z-ai/glm-5.3', 'zai-org/GLM-5.3', 'zai-glm-5-3', 'z-ai/glm-5.3:batch'),
        ('anthropic/claude-opus-4.5', 'claude-opus-4-5', 'claude-opus-4-5@20251101'),
        ('qwen/qwen3.6-27b', 'Qwen/Qwen3.6-27B', 'Qwen/Qwen3.6-27B-TEE', 'qwen3.6-27b'),
        ('google/gemma-4-31b-it:free', 'gemma-4-31b-it', 'google/gemma-4-31B-it'),
        ('meta-llama/llama-3.3-70b-instruct', 'meta/llama-3.3-70b-instruct-maas', 'meta-llama/Llama-3.3-70B-Instruct'),
        ('z-ai/glm-4.7-flash-free', 'z-ai/glm-4.7-flash', 'zai-org/GLM-4.7-Flash'),
        ('deepseek/deepseek-v4-flash', 'deepseek-ai/DeepSeek-V4-Flash', 'deepseek-v4-flash'),
    ]
    for group in same:
        keys = {canonical_id(x) for x in group}
        assert len(keys) == 1, (group, keys)
    different = [('z-ai/glm-5', 'z-ai/glm-5-turbo'), ('z-ai/glm-5.3', 'z-ai/glm-5.3-flash'),
                 ('~anthropic/claude-opus-latest', 'anthropic/claude-opus-5.5'), ('qwen/qwen-plus', 'qwen/qwen3.7-plus'),
                 ('openrouter/free', 'openrouter/auto'), ('openai/gpt-5.5', 'openai/gpt-5.5-pro')]
    for a, b in different:
        assert canonical_id(a) != canonical_id(b), (a, b, canonical_id(a))
    assert canonical_id('qwen/qwen-plus') == 'qwen-plus'                     # "qwen" è org, il nome resta intero
    assert canonical_id('') == '' and canonical_id(None) == ''
    m = merge([{'adapter': 'open_router', 'model_id': 'z-ai/glm-5.3'}, {'adapter': 'siliconflow', 'model_id': 'zai-org/GLM-5.3'},
               {'adapter': 'groq', 'model_id': 'qwen/qwen3.6-27b'}, {'adapter': 'x', 'model_id': ' '}])
    assert [len(v) for v in m.values()] == [2, 1] and 'glm-5-3' in m, m
    print('identity ok')


if __name__ == '__main__':
    _prova()
