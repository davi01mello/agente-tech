# Agente Tech 🤖📰

Agente que vigia a internet a cada 5 minutos e te avisa **na hora** quando sai uma notícia de tecnologia que realmente importa: lançamentos de IA, grandes movimentos do mercado e o ecossistema de Pernambuco.

```
GitHub Actions (a cada 5 min)
   └─ coleta 15 fontes em paralelo (sites oficiais, RSS, Google News, Hacker News)
       └─ descarta o que já viu (state/seen.json) e o que tem mais de 18h
           └─ Claude Haiku dá nota 0-10, marca urgência/duplicata e resume em PT-BR
               └─ nota ≥ 7 (≥ 6 para Pernambuco) → push no celular (ntfy) e/ou WhatsApp
```

## Setup (≈ 15 minutos)

### 1. Receber no celular (MVP com ntfy, grátis)
1. Instale o app **ntfy** (Android/iOS).
2. Toque em "+" e assine um tópico com nome difícil de adivinhar, ex.: `agente-tech-davi-8f3k29`. Qualquer pessoa que souber o nome consegue ler, então trate como senha.

### 2. Chave do Claude
Crie uma API key em https://console.anthropic.com → *API Keys* e coloque alguns dólares de crédito.

### 3. Repositório no GitHub
1. Crie um repositório **público** e envie estes arquivos (`git init && git add . && git commit -m "agente" && git push`).
   Em repositório público o GitHub Actions é ilimitado e grátis. Em privado, rodar a cada 5 min estoura os 2.000 min/mês gratuitos (se precisar ser privado, mude o cron para `*/30`). Os segredos ficam protegidos mesmo em repo público; o `state/seen.json` só guarda hashes.
2. *Settings → Secrets and variables → Actions → New repository secret*:
   - `ANTHROPIC_API_KEY`: sua chave
   - `NTFY_TOPIC`: o nome do tópico do passo 1
3. *Actions* → habilite os workflows → **Agente Tech → Run workflow** marcando "Enviar mensagem de teste". A notificação deve chegar no celular.
4. Rode mais uma vez **sem** marcar o teste. Essa primeira execução só "aprende" o que já existe (não dispara nada); a partir daí, só novidades chegam.

Pronto. O cron assume sozinho.

## Ajustes finos
| O quê | Onde |
|---|---|
| Adicionar/remover fontes | `agente/config.py` → `SOURCES` (fonte nova entra em silêncio, sem spam) |
| O que é relevante para você | `agente/config.py` → `INTEREST_PROFILE` (texto livre, o Claude lê) |
| Rigor do filtro | Variável `SCORE_MIN` (padrão 7) em *Settings → Variables* |
| Trocar o modelo | Variável `CLAUDE_MODEL` (padrão `claude-haiku-4-5`) |
| Ver o que foi avaliado | Aba *Actions* → execução → log com a nota de cada notícia |

Teste local: `pip install -r requirements.txt && python -m agente.main --dry-run` (mostra candidatas sem gastar API) e `python -m tests.test_pipeline` (teste offline do pipeline).

## Fase 2: WhatsApp (Meta Cloud API)
O código já está pronto; só falta a configuração na Meta:
1. https://developers.facebook.com → *Create App* → tipo **Business** → adicione o produto **WhatsApp**.
2. Em *WhatsApp → API Setup*: copie o **Phone number ID** e adicione seu número como destinatário de teste.
3. Gere um **token permanente**: *Business Settings → System users* → crie um usuário de sistema → *Generate token* com as permissões `whatsapp_business_messaging` e `whatsapp_business_management`.
4. Crie um **template** (*WhatsApp Manager → Message templates*), categoria *Utility*, idioma *Portuguese (BR)*, nome `alerta_noticia`, corpo:
   ```
   📰 {{1}}

   {{2}}

   💡 {{3}}

   🔗 {{4}}
   ```
   A aprovação costuma levar de minutos a 1 dia. O template é obrigatório porque a Meta só permite texto livre dentro de 24h após você mandar mensagem para o número.
5. No GitHub, adicione os secrets `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_TO` (formato `5581999999999`) e a variável `WHATSAPP_TEMPLATE=alerta_noticia`.

ntfy e WhatsApp podem ficar ativos ao mesmo tempo; para desligar um canal, apague o secret dele.

## Custos e limites
Com GitHub Actions público o custo de infraestrutura é zero. O Claude só é chamado quando aparece algo novo; a estimativa é de US$5–15/mês com Haiku, e dá para reduzir aumentando o intervalo do cron ou enxugando fontes do Google News. O WhatsApp cobra por conversa de template "utility" (centavos de real por mensagem no Brasil).

A latência típica entre a publicação e o alerta é de 5–15 minutos: o cron do GitHub pode atrasar em horários de pico e os feeds levam alguns minutos para atualizar. Para latência de ~1 minuto, o mesmo código roda num worker contínuo (Railway, VPS do CITi) com um loop `while True: run(); sleep(60)`.
