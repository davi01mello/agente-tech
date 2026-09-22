"""Teste offline do pipeline completo (sem rede, sem chave da API).

Rode: python -m tests.test_pipeline
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest import mock

tmp = tempfile.mkdtemp()
os.environ["STATE_FILE"] = os.path.join(tmp, "seen.json")

from agente import collect, config, main, notify  # noqa: E402

NOW = datetime.now(timezone.utc)


def rss(items):
    body = "".join(
        f"<item><title>{t}</title><link>{l}</link><description>{d}</description>"
        f"<pubDate>{format_datetime(p)}</pubDate></item>" for t, l, d, p in items)
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>{body}</channel></rss>'.encode()


PAGES = {"v1": '<a href="/news/claude-opus-5">...</a><a href="/news/old-post"><h3>Old post title here</h3></a><a href="/careers">x</a>',
         "v2": '<a href="/news/claude-opus-5-5"><h3>Introducing Claude Opus 5.5</h3></a>'
               '<a href="/news/claude-opus-5">...</a><a href="/news/old-post"><h3>Old post title here</h3></a>'}
FEEDS = {"v1": [("Old news", "https://ex.com/old", "x", NOW - timedelta(hours=1))],
         "v2": [("Old news", "https://ex.com/old", "x", NOW - timedelta(hours=1)),
                ("Porto Digital anuncia novo hub de IA em Recife", "https://ex.com/pd", "hub", NOW),
                ("10 gadgets para comprar", "https://ex.com/gadgets", "promo", NOW),
                ("Notícia antiga que entrou tarde", "https://ex.com/velha", "x", NOW - timedelta(days=3))]}
version = {"v": "v1"}


class Resp:
    def __init__(self, content):
        self.content = content
        self.text = content.decode() if isinstance(content, bytes) else content
        self.status_code = 200

    def raise_for_status(self):
        pass


def fake_get(url, **kw):
    if "anthropic.com" in url:
        return Resp(PAGES[version["v"]].encode())
    if "mistral.ai" in url:
        return Resp(PAGES["v1"].encode())
    if "hnrss" in url:
        raise ConnectionError("fonte fora do ar (simulado)")
    return Resp(rss(FEEDS[version["v"]]))


def fake_classify(cands, sent):
    out = {}
    for c in cands:
        t = c["title"].lower()
        nota = 10 if "opus" in t else 8 if "porto digital" in t else 2
        out[c["id"]] = {"id": c["id"], "nota": nota, "urgente": nota == 10, "repetida": False,
                        "categoria": "IA" if nota == 10 else "Pernambuco" if nota == 8 else "Mercado Tech",
                        "titulo_pt": c["title"], "resumo": "Resumo.", "por_que_importa": "Impacto."}
    return out


sent = []
with mock.patch.object(collect.requests, "get", fake_get), \
        mock.patch("agente.classify.classify", fake_classify), \
        mock.patch.object(notify, "CHANNELS", [("fake", lambda n: sent.append(n))]):
    # 1ª execução: todas as fontes são novas -> inicializa em silêncio
    assert main.run() == 0
    assert sent == [], "bootstrap não deveria disparar"
    state = json.load(open(os.environ["STATE_FILE"]))
    assert len(state["sources"]) == len(config.SOURCES) - 1  # HN falhou, não foi inicializado

    # 2ª execução: surgem novidades
    version["v"] = "v2"
    assert main.run() == 0
    urls = [n["url"] for n in sent]
    print("Enviadas:", *urls, sep="\n  ")
    assert "https://www.anthropic.com/news/claude-opus-5-5" in urls
    assert "https://ex.com/pd" in urls
    assert "https://ex.com/gadgets" not in urls, "nota baixa não deve ir"
    assert "https://ex.com/velha" not in urls, "item velho não deve ir"
    assert sent[0]["urgente"], "urgente deve sair primeiro"
    n_first = len(sent)

    # 3ª execução: nada novo -> não reenviar
    assert main.run() == 0
    assert len(sent) == n_first, "não pode reenviar"

print("\nExemplo de mensagem:\n" + notify.format_text(sent[0]))
print("\n✅ Todos os testes passaram")
sys.exit(0)
