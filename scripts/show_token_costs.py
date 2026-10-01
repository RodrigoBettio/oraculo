import json
import sys
from pathlib import Path

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = Path("/app/data/token_usage.json")
    if not p.exists():
        print("Arquivo de tokens não encontrado.")
        return

    data = json.loads(p.read_text(encoding='utf-8'))
    recs = data.get("records", [])

    total_tokens = sum(r.get("total_tokens", 0) for r in recs)
    total_usd = sum(r.get("cost_usd", 0.0) for r in recs)
    total_brl = sum(r.get("cost_brl", 0.0) for r in recs)

    # Agrupado por modelo
    by_model = {}
    for r in recs:
        m = r.get("model", "unknown")
        if m not in by_model:
            by_model[m] = {"calls": 0, "tokens": 0, "usd": 0.0, "brl": 0.0}
        by_model[m]["calls"] += 1
        by_model[m]["tokens"] += r.get("total_tokens", 0)
        by_model[m]["usd"] += r.get("cost_usd", 0.0)
        by_model[m]["brl"] += r.get("cost_brl", 0.0)

    # Agrupado por curso / agente
    by_agent = {}
    for r in recs:
        det = r.get("details", "")
        agent = "Outros"
        if "Jordan" in det:
            agent = "Jordan Belford"
        elif "Bruno" in det or "Codex" in det or "Claude" in det:
            agent = "Bruno (Codex/Claude)"
        elif "Tráfego" in det or "Sobral" in det or "Aula" in det:
            agent = "Sobral (Tráfego)"
        elif "Alex" in det or "Vance" in det:
            agent = "Alex Vance"

        if agent not in by_agent:
            by_agent[agent] = {"calls": 0, "usd": 0.0, "brl": 0.0}
        by_agent[agent]["calls"] += 1
        by_agent[agent]["usd"] += r.get("cost_usd", 0.0)
        by_agent[agent]["brl"] += r.get("cost_brl", 0.0)

    print("==========================================")
    print("       RAIO-X DE GASTOS NA API GEMINI     ")
    print("==========================================")
    print(f"Total de Chamadas Processadas: {len(recs)}")
    print(f"Total de Tokens Consumidos: {total_tokens:,}")
    print(f"Gasto Total Acumulado (USD): ${total_usd:.4f}")
    print(f"Gasto Total Acumulado (BRL): R$ {total_brl:.2f}")
    print("\n--- Gasto por Modelo Utilizado ---")
    for m, st in by_model.items():
        print(f"• {m}: {st['calls']} chamadas | {st['tokens']:,} tokens | ${st['usd']:.4f} USD (R$ {st['brl']:.2f})")

    print("\n--- Gasto por Curso / Especialista ---")
    for a, st in by_agent.items():
        print(f"• {a}: {st['calls']} aulas | ${st['usd']:.4f} USD (R$ {st['brl']:.2f})")

    # Média de custo por aula
    if recs:
        avg_usd = total_usd / len(recs)
        avg_brl = total_brl / len(recs)
        print(f"\n💡 Custo Médio por Aula: ${avg_usd:.4f} USD (~R$ {avg_brl:.2f})")

if __name__ == "__main__":
    main()
