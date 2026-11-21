"""The web for a consult (`spawn consult --web`): three tools a model can call while it answers, one rate for the whole process.

    search_web(query)      results of a general search (DuckDuckGo's HTML page: no key)
    search_arxiv(query)    papers from arXiv's API, newest first
    read_page(url)         the text of one page, its markup taken away

What the model asks goes out to DuckDuckGo, arXiv or the page it names: nothing else of the room does. Standard library only."""
import html
import json
import re
import threading
import time
import urllib.parse
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (compatible; chatroom-consult/1.1)'}
GAP = {'arxiv': 3.0, 'ddg': 2.0, 'page': 0.5}       # seconds between two calls of one backend, for the whole process (arXiv asks 3)
PAGE_CHARS = 20000
_lock, _last = threading.Lock(), {}

TOOLS = [
    {'type': 'function', 'function': {'name': 'search_web', 'description': 'Search the web. Returns titles, links and snippets.',
                                      'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']}}},
    {'type': 'function', 'function': {'name': 'search_arxiv', 'description': 'Search arXiv papers. Returns titles, ids, dates and abstracts.',
                                      'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']}}},
    {'type': 'function', 'function': {'name': 'read_page', 'description': 'Read the text of a web page (http or https).',
                                      'parameters': {'type': 'object', 'properties': {'url': {'type': 'string'}}, 'required': ['url']}}},
]


def _wait(backend):
    with _lock:
        now = time.time()
        sleep = _last.get(backend, 0) + GAP[backend] - now
        _last[backend] = max(now, _last.get(backend, 0) + GAP[backend])
    if sleep > 0:
        time.sleep(sleep)


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(2_000_000).decode(r.headers.get_content_charset() or 'utf-8', 'replace')


def text_of(page):
    """the readable text of an HTML page"""
    page = re.sub(r'(?is)<(script|style|noscript|svg|head)\b.*?</\1>', ' ', page)
    page = re.sub(r'(?i)<(br|p|div|li|h[1-6]|tr)\b[^>]*>', '\n', page)
    page = html.unescape(re.sub(r'<[^>]+>', ' ', page))
    return re.sub(r'\n\s*\n+', '\n\n', re.sub(r'[ \t\r\f\v]+', ' ', page)).strip()


def search_web(query, get=_get):
    _wait('ddg')
    page = get('https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(query))
    out = []
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=class="result__a"|\Z)', page, re.S):
        link, title, rest = m.groups()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(html.unescape(link)).query).get('uddg')
        snip = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.S)
        out.append(f"- {text_of(title)}\n  {q[0] if q else html.unescape(link)}\n  {text_of(snip[1]) if snip else ''}")
        if len(out) == 8:
            break
    return '\n'.join(out) or 'no results'


def search_arxiv(query, get=_get):
    _wait('arxiv')
    url = ('http://export.arxiv.org/api/query?sortBy=submittedDate&sortOrder=descending&max_results=8&search_query='
           + urllib.parse.quote('all:' + query))
    out = []
    for e in re.findall(r'<entry>(.*?)</entry>', get(url), re.S):
        f = lambda tag: text_of((re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', e, re.S) or ['', ''])[1])
        out.append(f"- {f('title')} ({f('published')[:10]})\n  {f('id')}\n  {f('summary')[:500]}")
    return '\n'.join(out) or 'no results'


def read_page(url, get=_get):
    if not re.match(r'https?://', url or ''):
        return 'refused: only http and https pages'
    _wait('page')
    text = text_of(get(url))
    return text[:PAGE_CHARS] + (f'\n[... {len(text) - PAGE_CHARS} more characters]' if len(text) > PAGE_CHARS else '')


def run(call, impl=None):
    """the text answer to one tool call {'name', 'arguments'}; an error is told to the model, never raised"""
    impl = impl or {'search_web': search_web, 'search_arxiv': search_arxiv, 'read_page': read_page}
    name = call.get('name') or (call.get('function') or {}).get('name')
    raw = call.get('arguments') if 'arguments' in call else (call.get('function') or {}).get('arguments')
    try:
        args = raw if isinstance(raw, dict) else json.loads(raw or '{}')
        fn = impl[name]
        return fn(args.get('url') if name == 'read_page' else args.get('query', ''))
    except KeyError:
        return f'unknown tool {name}: use search_web, search_arxiv or read_page'
    except Exception as exc:                          # a page that does not answer must not end the answer
        return f'error: {type(exc).__name__}: {str(exc)[:200]}'
