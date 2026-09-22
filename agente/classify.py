"""Triagem com Claude: nota de relevância, urgência e resumo em PT-BR."""
import json
import logging
import os
import re

from . import config

log = logging.getLogger(__name__)

TOOL = {
    "name": "avaliar_noticias",
    "description": "Registra a avaliação de cada notícia candidata.",
    "input_schema": {
        "type": "object",
        "properties": {
            "avaliacoes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "nota": {"type": "integer", "minimum": 0, "maximum": 10,
                                 "description": "Relevância para o perfil. 9-10 = lançamento/fato que muda o jogo; 7-8 = importante; <=6 = não vale alerta."},
                        "urgente": {"type": "boolean", "description": "true se é um anúncio de primeira mão que vale saber AGORA (ex.: lançamento de modelo)."},
                        "repetida": {"type": "boolean", "description": "true se é o mesmo fato de uma notícia já enviada ou de outra candidata com id menor."},
                        "categoria": {"type": "string", "enum": ["IA", "Mercado Tech", "Dev & Ferramentas", "Regulação", "Pernambuco", "Brasil"]},
                        "titulo_pt": {"type": "string", "description": "Título curto em português. Sem emoji, sem travessão (—)."},
                        "resumo": {"type": "string", "description": "1-2 frases objetivas em português: o que aconteceu. Sem emoji, sem travessão (—)."},
                        "por_que_importa": {"type": "string", "description": "1 frase sobre a aplicabilidade/impacto prático. Sem emoji, sem travessão (—)."},
                    },
                    "required": ["id", "nota", "urgente", "repetida", "categoria", "titulo_pt", "resumo", "por_que_importa"],
                },
            }
        },
        "required": ["avaliacoes"],
    },
}

SYSTEM = f"""Você é um curador de notícias de tecnologia extremamente criterioso.
Avalie cada candidata para o leitor abaixo. Seja exigente: a maioria das notícias NÃO merece alerta.
Priorize fatos novos e de primeira mão (anúncios oficiais > cobertura > opinião).

PERFIL DO LEITOR:
{config.INTEREST_PROFILE}

Marque "repetida"=true quando o fato já está na lista de JÁ ENVIADAS ou quando duas candidatas
falam do mesmo fato (mantenha só a de fonte mais primária/completa como não-repetida).

Ao escrever titulo_pt, resumo e por_que_importa: escreva como alguém mandando uma mensagem rápida
pra um colega, não como uma IA. Nunca use emoji. Nunca use travessão (—) nem reticências (...);
use frases curtas, separadas por ponto ou vírgula. Não use adjetivo de hype ("revolucionário",
"incrível", "poderoso", "impressionante"). Vá direto ao fato."""

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "]+",
    flags=re.UNICODE,
)


def _sanitize(text: str) -> str:
    """Rede de segurança: tira emoji e travessão mesmo se o modelo ignorar a instrução."""
    if not isinstance(text, str):
        return text
    text = _EMOJI_RE.sub("", text)
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    text = re.sub(r"\.{2,}", ".", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def classify(candidates: list[dict], recent_sent: list[str]) -> dict[str, dict]:
    """Retorna {id: avaliacao}. Processa em lotes para caber no contexto."""
    if not candidates:
        return {}
    import anthropic  # import tardio: permite --dry-run sem a lib/chave

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    out: dict[str, dict] = {}
    for i in range(0, len(candidates), 25):
        batch = candidates[i:i + 25]
        payload = [{
            "id": c["id"], "fonte": c["source"], "grupo": c["group"], "titulo": c["title"],
            "trecho": c["summary"][:300], "url": c["url"],
        } for c in batch]
        user = ("JÁ ENVIADAS RECENTEMENTE:\n" + ("\n".join(f"- {t}" for t in recent_sent[-40:]) or "(nenhuma)")
                + "\n\nCANDIDATAS:\n" + json.dumps(payload, ensure_ascii=False, indent=1))
        msg = client.messages.create(
            model=config.CLAUDE_MODEL, max_tokens=4096, system=SYSTEM,
            tools=[TOOL], tool_choice={"type": "tool", "name": "avaliar_noticias"},
            messages=[{"role": "user", "content": user}],
        )
        for block in msg.content:
            if block.type == "tool_use":
                for av in block.input.get("avaliacoes", []):
                    for k in ("titulo_pt", "resumo", "por_que_importa"):
                        if k in av:
                            av[k] = _sanitize(av[k])
                    out[av["id"]] = av
        log.info("Lote %d: %d avaliadas (tokens in=%s out=%s)", i // 25 + 1, len(batch),
                 msg.usage.input_tokens, msg.usage.output_tokens)
    return out
