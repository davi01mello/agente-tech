"""Configuração do agente: fontes, limiares e perfil de interesse.

Para adicionar/remover fontes, edite as listas abaixo. Uma fonte nova é
"silenciosamente inicializada" na primeira execução (não dispara o que já
existia nela), então é seguro adicionar fontes a qualquer momento.
"""
import os
from urllib.parse import quote_plus


def gnews(query: str, lang: str = "pt") -> str:
    """URL de RSS do Google News para uma busca (só últimas 24h)."""
    q = quote_plus(f"{query} when:1d")
    if lang == "pt":
        return f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


# kind: "rss" (feed RSS/Atom) ou "page" (monitora links novos numa página sem RSS)
# group: "oficial" (fonte primária, anúncio sai aqui primeiro), "global", "brasil", "pernambuco"
SOURCES = [
    # --- Fontes oficiais dos laboratórios de IA (onde o lançamento aparece primeiro) ---
    {"name": "Anthropic", "kind": "page", "url": "https://www.anthropic.com/news",
     "link_pattern": r"^/news/[a-z0-9-]+$", "group": "oficial"},
    {"name": "OpenAI", "kind": "rss", "url": "https://openai.com/news/rss.xml", "group": "oficial"},
    {"name": "Google DeepMind", "kind": "rss", "url": "https://deepmind.google/blog/rss.xml", "group": "oficial"},
    {"name": "Google AI", "kind": "rss", "url": "https://blog.google/technology/ai/rss/", "group": "oficial"},
    {"name": "Mistral", "kind": "page", "url": "https://mistral.ai/news",
     "link_pattern": r"^/news/[a-z0-9-]+/?$", "group": "oficial"},
    {"name": "Hugging Face", "kind": "rss", "url": "https://huggingface.co/blog/feed.xml", "group": "oficial"},

    # --- Radar global rápido ---
    {"name": "Hacker News (150+ pts)", "kind": "rss", "url": "https://hnrss.org/newest?points=150", "group": "global"},
    {"name": "TechCrunch AI", "kind": "rss", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "group": "global"},
    {"name": "The Verge AI", "kind": "rss", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "group": "global"},
    {"name": "Google News – lançamentos IA", "kind": "rss",
     "url": gnews('(Anthropic OR OpenAI OR "Google Gemini" OR DeepSeek OR Meta AI OR xAI) (launch OR releases OR announces OR unveils)', "en"),
     "group": "global"},

    # --- Brasil ---
    {"name": "Tecnoblog", "kind": "rss", "url": "https://tecnoblog.net/feed/", "group": "brasil"},
    {"name": "Google News – IA Brasil", "kind": "rss",
     "url": gnews('"inteligência artificial" (lança OR anuncia OR startup OR investimento)'), "group": "brasil"},

    # --- Ecossistema pernambucano ---
    {"name": "Google News – Porto Digital", "kind": "rss", "url": gnews('"Porto Digital"'), "group": "pernambuco"},
    {"name": "Google News – Tech Recife/PE", "kind": "rss",
     "url": gnews('(Recife OR Pernambuco) (startup OR tecnologia OR inovação OR "inteligência artificial")'),
     "group": "pernambuco"},
    {"name": "Google News – CESAR/CIn/CITi", "kind": "rss",
     "url": gnews('("CESAR School" OR "CESAR Recife" OR "CIn UFPE" OR "CITi UFPE" OR "Softex Pernambuco" OR "Rec\'n\'Play")'),
     "group": "pernambuco"},
]

# Perfil de interesse enviado ao Claude para calibrar a relevância.
INTEREST_PROFILE = """
Sou do CITi (empresa júnior de tecnologia da UFPE, Recife-PE). Quero saber IMEDIATAMENTE de:
- Lançamentos de modelos de IA e produtos relevantes (Anthropic/Claude, OpenAI/GPT, Google/Gemini,
  Meta/Llama, DeepSeek, Mistral, xAI etc.), novas APIs, ferramentas de dev com IA, agentes.
- Movimentos grandes do mercado tech: aquisições, rodadas grandes, regulação de IA (Brasil/UE/EUA),
  mudanças de preço/política de plataformas que afetam quem desenvolve software.
- Ecossistema de Pernambuco: Porto Digital, CESAR, CIn-UFPE, startups de Recife, editais, eventos
  (Rec'n'Play etc.), investimentos e programas de inovação no estado.
NÃO quero: reviews de gadgets, promoções, fofoca de celebridade tech, opinião genérica, listas
"10 ferramentas", notícias requentadas, conteúdo patrocinado, tutoriais básicos.
""".strip()

# Nota mínima (0-10) para disparar. Pernambuco tem régua um pouco menor por ser nicho.
SCORE_MIN = int(os.getenv("SCORE_MIN", "7"))
SCORE_MIN_PERNAMBUCO = int(os.getenv("SCORE_MIN_PERNAMBUCO", "6"))

# Ignora itens publicados há mais que isso (evita notícia velha que só agora entrou no feed).
MAX_AGE_HOURS = int(os.getenv("MAX_AGE_HOURS", "18"))

# Modelo usado na triagem (rápido e barato). Pode trocar via variável de ambiente.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")

# Limite de segurança de mensagens por execução (evita spam se algo der errado).
MAX_ALERTS_PER_RUN = int(os.getenv("MAX_ALERTS_PER_RUN", "8"))

STATE_FILE = os.getenv("STATE_FILE", "state/seen.json")
