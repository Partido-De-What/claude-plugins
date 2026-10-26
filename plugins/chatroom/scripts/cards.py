"""Cards in the chat: a message of kind 'card' that the viewer draws as an interactive box (cards.js), with a plain text for
everyone who cannot draw it (agents, friends, the /stanza pane, the transcript).

A card is {type, id, data}. data is what the producer wants shown, as generic blocks the viewer knows how to draw:
  {"title": "...", "icon": "🔑", "blocks": [
     {"t": "text", "text": "..."},
     {"t": "rows", "rows": [{"key": "openrouter", "label": "OpenRouter", "value": "20 free", "state": "ok|bad|warn|wait",
                             "link": "https://...", "fields": [...], "actions": [{"id": "verify", "label": "...", "confirm": "..."}]}]},
     {"t": "form", "fields": [{"name": "key", "label": "...", "type": "text|password|select|number", "options": [...]}],
                   "submit": {"id": "save", "label": "..."}},
     {"t": "bars", "unit": "pts", "items": [{"label": "...", "value": 61.2, "max": 100, "note": "..."}]},
     {"t": "actions", "items": [{"id": "...", "label": "...", "confirm": "..."}]}]}
ROOM/cards.json keeps each card's state, written only here and under the room's lock: what the card shows now in place of
its first data (the producer's answers to actions), and done/dismissed. A click is POST /card_action {id, action, key, values}:
the module of the card's type answers it (CARD_TYPES), its answer becomes the new state. What a field carries (a key typed
in a password field) goes to that module and nowhere else: never into cards.json, the chat, a log or an answer."""
import importlib
import json
import re
import secrets

CARD_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,47}\Z')
NAME = re.compile(r'[a-z][a-z0-9_]{0,31}\Z')
DATA_MAX, BODY_MAX = 64 * 1024, 16 * 1024
SECRET = re.compile(r'sk-or-v1-|sk-ant-|\bsk-[A-Za-z0-9_-]{20,}|\bnvapi-|\bgsk_[A-Za-z0-9]{20,}|\bAIza[0-9A-Za-z_-]{30,}|\bhf_[A-Za-z0-9]{30,}')
# the module that answers each type of card (it defines card_action(room, card, action, key, values) -> new data, or raises
# ValueError with what to tell the user); None: a card that only shows. A type not listed here cannot be posted.
CARD_TYPES = {'demo': None, 'model_sheet': None, 'compare': None, **dict.fromkeys(('prepare_spawn', 'catalog', 'create_role', 'role_state', 'replace'), 'spawn.cards_spawn')}


def _check_text(what, value):
    """nothing that looks like a key ever reaches the chat or cards.json"""
    if SECRET.search(json.dumps(value, ensure_ascii=False)):
        raise ValueError(f'{what} looks like it holds a key: refused')
    return value


def post(room, author, ctype, data, text, card_id=None):
    """a card in the chat; returns (n, id). text is what is read where the card cannot be drawn"""
    if ctype not in CARD_TYPES:
        raise ValueError(f'unknown card type {ctype!r}')
    cid = card_id or f'{ctype.replace("_", "-")}-{secrets.token_hex(3)}'
    if not CARD_ID.match(cid):
        raise ValueError(f'bad card id {cid!r}')
    if not isinstance(data, dict) or len(json.dumps(data, ensure_ascii=False)) > DATA_MAX:
        raise ValueError('card data must be an object of at most 64 KB')
    text = ' '.join(str(text or '').split())[:500]
    if not text:
        raise ValueError('a card needs its plain text')
    _check_text('the card', [data, text])
    n = room.append(author, text, 'card', flags={'card': {'type': ctype, 'id': cid, 'data': data}})
    return n, cid


def states(room):
    from chat import read_json
    try:
        d = read_json(room.dir / 'cards.json', {})
    except (OSError, ValueError):
        d = {}
    return d if isinstance(d, dict) else {}


def _save(room, cid, state):
    from chat import write_atomic

    def run():
        d = states(room)
        d[cid] = state
        write_atomic(room.dir / 'cards.json', json.dumps(d, ensure_ascii=False))
    room.locked(run)


def find(room, cid):
    return next((m for m in reversed(room.messages()) if m.get('kind') == 'card' and (m.get('card') or {}).get('id') == cid), None)


def action(room, body):
    """a click from the viewer: {id, action, key, values}. Returns the card's new state; ValueError with what to show"""
    if not isinstance(body, dict) or len(json.dumps(body, ensure_ascii=False)) > BODY_MAX:
        raise ValueError('bad card action')
    cid, act, key = str(body.get('id', '')), str(body.get('action', '')), str(body.get('key') or '')[:64]
    values = body.get('values') or {}
    if not CARD_ID.match(cid) or not NAME.match(act) or not isinstance(values, dict):
        raise ValueError('bad card action')
    values = {str(k)[:40]: str(v)[:2000] for k, v in list(values.items())[:20]}
    m = find(room, cid)
    if not m:
        raise ValueError('no such card')
    card = m['card']
    old = states(room).get(cid) or {}
    if act in ('dismiss', 'reopen'):                       # every card can be put away, and opened again
        new = {**old, 'dismissed': act == 'dismiss'}
    else:
        mod = CARD_TYPES.get(card['type'])
        if not mod:
            raise ValueError('this card has no actions')
        answer = importlib.import_module(mod).card_action(room, {**card, 'state': old}, act, key, values)
        if not isinstance(answer, dict):
            raise ValueError('the card did not answer')
        new = {**old, **answer}
    _check_text('the answer', new)                          # a module that echoes a key never writes it anywhere
    _save(room, cid, new)
    return new


def _prova():
    """self-check: post, plain text, refused keys, actions answered by a module, dismiss, bad input"""
    import sys
    import tempfile
    import types
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import chat
    with tempfile.TemporaryDirectory() as tmp:
        room = chat.Room(tmp)
        room.save_config({'participants': ['A'], 'user_name': 'USER', 'self_names': ['LEAD']})
        seen = {}
        fake = types.ModuleType('fake_cards')

        def card_action(room, card, act, key, values):
            seen['values'] = values
            if act == 'verify':
                return {'blocks': [{'t': 'text', 'text': 'ok ' + key}]}
            if act == 'leak':
                return {'blocks': [{'t': 'text', 'text': values['key']}]}
            raise ValueError('nope')
        fake.card_action = card_action
        sys.modules['fake_cards'] = fake
        CARD_TYPES['probe'] = 'fake_cards'
        n, cid = post(room, 'LEAD', 'probe', {'title': 'Keys', 'blocks': []}, 'Keys: 0 of 3 set')
        m = room.messages()[-1]
        assert m['kind'] == 'card' and m['card']['id'] == cid and m['text'] == 'Keys: 0 of 3 set' and cid.startswith('probe-')
        for bad in (lambda: post(room, 'LEAD', 'nope', {}, 'x'), lambda: post(room, 'LEAD', 'probe', {}, ''),
                    lambda: post(room, 'LEAD', 'probe', {'k': 'sk-or-v1-' + 'a' * 40}, 'x'), lambda: post(room, 'LEAD', 'probe', {}, 'x', 'Bad Id'),
                    lambda: action(room, {'id': cid, 'action': 'x y'}), lambda: action(room, {'id': 'missing', 'action': 'go'}),
                    lambda: action(room, {'id': cid, 'action': 'other'})):
            try:
                bad()
            except ValueError:
                continue
            raise AssertionError('accepted a bad card or action')
        st = action(room, {'id': cid, 'action': 'verify', 'key': 'openrouter', 'values': {'key': 'sk-or-v1-' + 'b' * 40}})
        assert st['blocks'][0]['text'] == 'ok openrouter' and seen['values']['key'].startswith('sk-or-v1-')
        try:
            action(room, {'id': cid, 'action': 'leak', 'values': {'key': 'sk-or-v1-' + 'c' * 40}})
            raise AssertionError('a key echoed by a module was saved')
        except ValueError:
            pass
        assert 'sk-or-v1-' not in (room.dir / 'cards.json').read_text(encoding='utf-8') + room.chat.read_text(encoding='utf-8')
        assert action(room, {'id': cid, 'action': 'dismiss'})['dismissed'] is True and states(room)[cid]['blocks']
        assert action(room, {'id': cid, 'action': 'reopen'})['dismissed'] is False
        assert not room.wakes(m, 'A') and not room.concerns(m, 'A'), 'a card wakes or concerns an agent'
    print('cards ok')


if __name__ == '__main__':
    _prova()
