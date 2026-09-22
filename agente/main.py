"""Ciclo do agente: coleta -> filtra novos -> Claude avalia -> dispara.

Uso:
  python -m agente.main               # execução normal
  python -m agente.main --dry-run     # coleta e mostra candidatos, sem Claude e sem salvar estado
  python -m agente.main --test-notify # envia uma mensagem de teste nos canais configurados
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from . import config
from .collect import collect_all
from .notify import dispatch

log = logging.getLogger("agente")
NOW = datetime.now(timezone.utc)
KEEP_DAYS = 10


def load_state() -> dict:
    try:
        with open(config.STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"seen": {}, "sources": [], "sent": []}


def save_state(state: dict) -> None:
    cutoff = (NOW - timedelta(days=KEEP_DAYS)).isoformat()
    state["seen"] = {k: v for k, v in state["seen"].items() if v >= cutoff}
    state["sent"] = [s for s in state["sent"] if s["ts"] >= cutoff][-200:]
    os.makedirs(os.path.dirname(config.STATE_FILE) or ".", exist_ok=True)
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=0, sort_keys=True)


def run(dry_run: bool = False) -> int:
    state = load_state()
    results, errors = collect_all(config.SOURCES)
    known_sources = set(state["sources"])
    now_iso = NOW.isoformat()
    max_age = NOW - timedelta(hours=config.MAX_AGE_HOURS)

    candidates, seen_ids = [], set()
    for src in config.SOURCES:
        items = results.get(src["name"], [])
        bootstrap = src["name"] not in known_sources
        for it in items:
            if it["id"] in seen_ids:
                continue
            seen_ids.add(it["id"])
            is_new = it["id"] not in state["seen"]
            state["seen"][it["id"]] = now_iso  # renova: enquanto aparecer na fonte, não reenvia
            if not is_new or bootstrap:
                continue
            if it["published"] and it["published"] < max_age:
                continue
            candidates.append(it)
        if items and bootstrap:
            log.info("Fonte nova inicializada em silêncio: %s (%d itens)", src["name"], len(items))
            state["sources"].append(src["name"])

    log.info("Candidatas novas: %d | fontes com erro: %d", len(candidates), len(errors))
    if dry_run:
        for c in candidates:
            print(f"- [{c['group']}/{c['source']}] {c['title']}\n  {c['url']}")
        return 0

    if candidates:
        from .classify import classify
        try:
            evals = classify(candidates, [s["title"] for s in state["sent"]])
        except Exception as exc:
            # Não salva estado: na próxima execução as candidatas serão reavaliadas.
            log.error("Falha na triagem com Claude: %s", exc)
            return 1

        chosen = []
        for c in candidates:
            ev = evals.get(c["id"])
            if not ev or ev.get("repetida"):
                continue
            minimum = config.SCORE_MIN_PERNAMBUCO if c["group"] == "pernambuco" or ev["categoria"] == "Pernambuco" else config.SCORE_MIN
            if ev["nota"] >= minimum:
                chosen.append({**c, **ev})
            log.info("  %2d %s %s", ev["nota"], "✅" if ev["nota"] >= minimum else "  ", c["title"][:90])

        chosen.sort(key=lambda n: (n["urgente"], n["nota"]), reverse=True)
        for n in chosen[:config.MAX_ALERTS_PER_RUN]:
            dispatch(n)
            state["sent"].append({"title": n["titulo_pt"], "url": n["url"], "ts": now_iso})
        log.info("Alertas enviados: %d", min(len(chosen), config.MAX_ALERTS_PER_RUN))

    save_state(state)
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test-notify", action="store_true")
    args = ap.parse_args()
    if args.test_notify:
        ok = dispatch({"titulo_pt": "Teste do Agente Tech", "resumo": "Se você recebeu isto, o canal está funcionando.",
                       "por_que_importa": "A partir de agora as notícias relevantes chegam aqui.",
                       "categoria": "IA", "urgente": False, "nota": 10, "source": "Agente Tech",
                       "url": "https://github.com"})
        sys.exit(0 if ok else 1)
    sys.exit(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
