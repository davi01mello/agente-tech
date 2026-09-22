"""Canais de envio. Ative via variáveis de ambiente (pode ter mais de um ao mesmo tempo).

- ntfy (MVP, push no celular, grátis):     NTFY_TOPIC
- WhatsApp Cloud API (Meta, fase 2):       WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_TO
                                            [WHATSAPP_TEMPLATE, WHATSAPP_TEMPLATE_LANG]
- Console (sempre ativo, aparece no log do GitHub Actions)
"""
import logging
import os

import requests

log = logging.getLogger(__name__)

EMOJI = {"IA": "🤖", "Mercado Tech": "📈", "Dev & Ferramentas": "🛠️", "Regulação": "⚖️",
         "Pernambuco": "🦀", "Brasil": "🇧🇷"}


def format_text(n: dict) -> str:
    head = "🚨 URGENTE · " if n["urgente"] else ""
    return (f"{head}{EMOJI.get(n['categoria'], '📰')} *{n['titulo_pt']}*\n\n"
            f"{n['resumo']}\n\n💡 {n['por_que_importa']}\n\n"
            f"📍 {n['source']} · nota {n['nota']}/10\n🔗 {n['url']}")


def send_ntfy(n: dict) -> None:
    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        return
    server = os.getenv("NTFY_SERVER", "https://ntfy.sh")
    body = {
        "topic": topic,
        "title": f"{EMOJI.get(n['categoria'], '📰')} {n['titulo_pt']}"[:250],
        "message": f"{n['resumo']}\n\n💡 {n['por_que_importa']}\n\n{n['source']} · {n['nota']}/10",
        "click": n["url"],
        "priority": 5 if n["urgente"] else 4 if n["nota"] >= 8 else 3,
        "tags": [n["categoria"].lower().replace(" ", "-")],
        "actions": [{"action": "view", "label": "Abrir notícia", "url": n["url"]}],
    }
    r = requests.post(server, json=body, timeout=15)
    r.raise_for_status()


def send_whatsapp(n: dict) -> None:
    token, phone_id, to = (os.getenv(k) for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "WHATSAPP_TO"))
    if not (token and phone_id and to):
        return
    version = os.getenv("WHATSAPP_API_VERSION", "v21.0")
    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    template = os.getenv("WHATSAPP_TEMPLATE")
    if template:
        # Template aprovado com 4 variáveis no corpo: {{1}} título, {{2}} resumo, {{3}} por que importa, {{4}} link
        params = [n["titulo_pt"], n["resumo"], n["por_que_importa"], n["url"]]
        payload = {"messaging_product": "whatsapp", "to": to, "type": "template",
                   "template": {"name": template, "language": {"code": os.getenv("WHATSAPP_TEMPLATE_LANG", "pt_BR")},
                                "components": [{"type": "body", "parameters": [
                                    {"type": "text", "text": p.replace("\n", " ")[:1000]} for p in params]}]}}
    else:
        # Texto livre: só funciona dentro da janela de 24h após você mandar msg para o número.
        payload = {"messaging_product": "whatsapp", "to": to, "type": "text",
                   "text": {"body": format_text(n), "preview_url": True}}
    r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=15)
    if r.status_code >= 400:
        raise RuntimeError(f"WhatsApp {r.status_code}: {r.text[:300]}")


CHANNELS = [("ntfy", send_ntfy), ("whatsapp", send_whatsapp)]


def dispatch(n: dict) -> bool:
    print("\n" + "=" * 60 + "\n" + format_text(n) + "\n" + "=" * 60, flush=True)
    ok = True
    for name, fn in CHANNELS:
        try:
            fn(n)
        except Exception as exc:
            ok = False
            log.error("Falha no canal %s: %s", name, exc)
    return ok
