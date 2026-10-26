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


def line_key(canonical):
    """(linea, versione) di una chiave comune: la linea è il nome senza i numeri di versione ma con i qualificatori e la
    taglia (coder, flash, mini, super, vl, 31b, a12b...), la versione la tupla dei numeri tolti. glm-5, glm-5-2, glm-5-3
    sono una linea; qwen3-coder, qwen3-8, qwen3-8-flash tre; gemma-4-31b-it e gemma-4-26b-a4b-it due. Nel dubbio una
    parola resta nella linea: due modelli si uniscono solo se tutto il resto del nome è uguale. La versione è
    ((numeri), (date)): una data (4 cifre o più: 2512, 0731, 20251101) conta solo a parità di numeri, così
    deepseek-v4-1-flash-1017 è più nuovo di deepseek-v4-flash-0731 e mistral-large-4-0 di mistral-large-2512"""
    words, version, dates = [], [], []
    for t in str(canonical or '').split('-'):
        if t.isdigit():
            (dates if len(t) >= 4 or dates else version).append(int(t))   # dopo una data (2025-07-28) tutto è data
            continue
        m = re.fullmatch(r'([a-z]+)(\d+)', t)             # qwen3, k3, o3, v4: nome attaccato alla versione
        if m and m[1] != 'v':
            words.append(m[1])
            version.append(int(m[2]))
        elif m:
            version.append(int(m[2]))                     # v4 di deepseek-v4-flash
        elif t:
            words.append(t)
    return '-'.join(words), (tuple(version), tuple(dates))


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
    lines = [  # #456 di Adrian, poi id veri di docs/adapter-modelli.md: ogni gruppo una linea
        ('glm-5', 'glm-5-2', 'glm-5-3'), ('nemotron-3-super-120b-a12b', 'nemotron-3-5-super-120b-a12b'),
        ('deepseek-v4-flash', 'deepseek-v4-1-flash'), ('claude-opus-4-5', 'claude-opus-5-5', 'claude-opus-5'),
        ('kimi-k2-6', 'kimi-k3'), ('qwen3-6-27b', 'qwen3-8-27b'), ('gemini-3-5-flash', 'gemini-3-8-flash'), ('o3-mini', 'o4-mini')]
    for group in lines:
        keys = {line_key(canonical_id(x))[0] for x in group}
        assert len(keys) == 1, (group, keys)
    apart = [('qwen3-coder', 'qwen3-8', 'qwen3-8-flash'), ('nemotron-3-super-120b-a12b', 'nemotron-3-ultra-550b-a55b'),
             ('gemma-4-31b-it', 'gemma-4-26b-a4b-it'), ('glm-5-3', 'glm-5-3-flash', 'glm-5-turbo'),
             ('gemini-3-5-flash', 'gemini-3-5-flash-lite'), ('gpt-oss-120b', 'gpt-oss-20b'), ('kimi-k3', 'kimi-k3-1-pro', 'kimi-k2-7-code'),
             ('claude-opus-5-5', 'claude-opus-latest'), ('nemotron-3-5-super-vl', 'nemotron-3-5-super'), ('llama-3-3-70b-instruct', 'llama-3-1-8b-instruct')]
    for group in apart:
        keys = [line_key(canonical_id(x))[0] for x in group]
        assert len(set(keys)) == len(keys), (group, keys)
    assert line_key('glm-5-3') == ('glm', ((5, 3), ())) and line_key('glm-5-3') > line_key('glm-5-2') > line_key('glm-5')
    assert line_key('deepseek-v4-1-flash') == ('deepseek-flash', ((4, 1), ())) and line_key('qwen3-coder') == ('qwen-coder', ((3,), ()))
    assert line_key('deepseek-v4-1-flash-1017') > line_key('deepseek-v4-flash-0731') and line_key('mistral-large-4-0') > line_key('mistral-large-2512')
    assert line_key('kimi-k3') > line_key('kimi-k2-0905') > line_key('kimi-k2') and line_key('') == ('', ((), ()))
    assert line_key('qwen3-7-plus') > line_key('qwen-plus-2025-07-28') and line_key('qwen-plus-2025-07-28')[0] == 'qwen-plus'   # #506 p.1
    print('identity ok')


if __name__ == '__main__':
    _prova()
