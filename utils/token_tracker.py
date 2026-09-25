import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import settings

TOKEN_LOG_FILE = settings.DATA_DIR / "token_usage.json"
_lock = threading.Lock()

# Cotas Oficiais do Google Gemini (Mundo Real)
FREE_TIER_MAX_RPD = 1500               # 1.500 requisições diárias gratuitas
FREE_TIER_TPM = 1_000_000              # 1M tokens/minuto
FREE_TIER_RPM = 15                     # 15 requisições/minuto
DEFAULT_FREE_TIER_BUDGET = 15_000_000  # Estimativa prática de tokens diários (~15M)
DEFAULT_PAID_TIER_BUDGET = 0           # 0 = Ilimitado (Pay-as-you-go sob demanda)

DEFAULT_DAILY_BUDGET = DEFAULT_FREE_TIER_BUDGET
DEFAULT_PLAN_TIER = "paid_tier"        # Padrão: pago/pay-as-you-go ou livre
USD_TO_BRL = 5.60

def _load_data() -> Dict[str, Any]:
    if not TOKEN_LOG_FILE.exists():
        return {
            "daily_budget": DEFAULT_PAID_TIER_BUDGET,
            "plan_tier": "paid_tier",
            "records": []
        }
    try:
        with open(TOKEN_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("plan_tier", "paid_tier")
            data.setdefault("records", [])

            data.setdefault("daily_budget", DEFAULT_PAID_TIER_BUDGET)
            return data
    except Exception:
        return {
            "daily_budget": DEFAULT_PAID_TIER_BUDGET,
            "plan_tier": "paid_tier",
            "records": []
        }

def _save_data(data: Dict[str, Any]):
    TOKEN_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def calculate_call_cost(model: str, prompt_tokens: int, output_tokens: int, source: str) -> float:
    """Calcula o custo estimado em USD com base na tabela oficial do Google Gemini."""
    # Preços por 1M tokens:
    # Gemini Flash: ~$0.15 a $0.30/1M texto, $1.00/1M áudio, $2.50/1M output
    # Gemini Pro: ~$1.25/1M prompt, $10.00/1M output
    model_lower = model.lower()
    if "pro" in model_lower:
        prompt_cost = (prompt_tokens / 1_000_000) * 1.25
        output_cost = (output_tokens / 1_000_000) * 10.00
    else:
        is_audio = "audio" in source.lower() or "study" in source.lower()
        prompt_rate = 1.00 if is_audio else 0.30
        prompt_cost = (prompt_tokens / 1_000_000) * prompt_rate
        output_cost = (output_tokens / 1_000_000) * 2.50

    return round(prompt_cost + output_cost, 6)

def record_tokens(
    source: str,
    details: str,
    prompt_tokens: int,
    output_tokens: int,
    total_tokens: Optional[int] = None,
    model: str = "gemini-3.6-flash"
) -> Dict[str, Any]:
    """Registra uma transação de consumo de tokens com custo calculado."""
    calc_total = total_tokens if total_tokens is not None and total_tokens > 0 else (prompt_tokens + output_tokens)
    cost_usd = calculate_call_cost(model, prompt_tokens, output_tokens, source)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "details": details,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": calc_total,
        "cost_usd": cost_usd,
        "cost_brl": round(cost_usd * USD_TO_BRL, 4)
    }

    with _lock:
        data = _load_data()
        data.setdefault("records", []).append(record)
        _save_data(data)

    return record

def format_number(val: int) -> str:
    """Formata número de tokens de forma compacta (ex: 12.5k, 1.2M)."""
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"{val / 1_000:.1f}k"
    return str(val)

def get_token_stats() -> Dict[str, Any]:
    """Calcula estatísticas completas de consumo diário, semanal, custos e histórico conforme o mundo real."""
    with _lock:
        data = _load_data()

    plan_tier = data.get("plan_tier", "paid_tier")
    budget = data.get("daily_budget", DEFAULT_PAID_TIER_BUDGET if plan_tier == "paid_tier" else DEFAULT_FREE_TIER_BUDGET)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    daily_used = 0
    daily_prompt = 0
    daily_output = 0
    daily_cost_usd = 0.0
    daily_requests = 0

    weekly_used = 0
    weekly_cost_usd = 0.0
    weekly_requests = 0

    total_all_time = 0
    total_cost_usd = 0.0

    all_records = data.get("records", [])

    for rec in all_records:
        try:
            ts = datetime.fromisoformat(rec.get("timestamp"))
            tok = rec.get("total_tokens", 0)
            p_tok = rec.get("prompt_tokens", 0)
            o_tok = rec.get("output_tokens", 0)
            c_usd = rec.get("cost_usd", 0.0)

            total_all_time += tok
            total_cost_usd += c_usd

            if ts >= week_start:
                weekly_used += tok
                weekly_cost_usd += c_usd
                weekly_requests += 1

            if ts >= today_start:
                daily_used += tok
                daily_prompt += p_tok
                daily_output += o_tok
                daily_cost_usd += c_usd
                daily_requests += 1
        except Exception:
            continue

    # Cálculo da porcentagem de uso real
    if plan_tier == "paid_tier":
        if budget and budget > 0:
            real_pct = round((daily_used / budget) * 100, 1)
            is_exceeded = (daily_used >= budget)
        else:
            real_pct = None  # Ilimitado sob demanda
            is_exceeded = False
    else:
        # Free Tier: compara com 1.500 RPD ou o budget estimado de 15M
        effective_budget = budget if (budget and budget > 0) else DEFAULT_FREE_TIER_BUDGET
        real_pct = round((daily_used / effective_budget) * 100, 1)
        is_exceeded = (daily_used >= effective_budget or daily_requests >= FREE_TIER_MAX_RPD)

    safety_lock = data.get("safety_lock", False)

    # Últimas 25 chamadas para o dashboard
    recent_records = all_records[-25:]
    recent_records.reverse()

    # Informações oficiais sobre a cota do plano no Google Gemini
    if plan_tier == "paid_tier":
        tier_info = {
            "name": "Pay-as-you-go (Tier 1 / Google Cloud)",
            "rpm_limit": "1.000 a 2.000 RPM (Requisições/min)",
            "tpm_limit": "4.000.000 TPM (4M tokens/min)",
            "rpd_limit": "Ilimitado sob demanda",
            "daily_requests_str": f"{daily_requests} requisições hoje (sem limite)",
            "description": "No Google Cloud Pay-as-you-go NÃO há limite diário de tokens. O processamento é sob demanda e custa apenas centavos por milhão."
        }
    else:
        req_pct = round((daily_requests / FREE_TIER_MAX_RPD) * 100, 1)
        tier_info = {
            "name": "Plano Gratuito (Google AI Studio Free Tier)",
            "rpm_limit": "15 RPM (Requisições/min)",
            "tpm_limit": "1.000.000 TPM (1M tokens/min)",
            "rpd_limit": f"{daily_requests} / {FREE_TIER_MAX_RPD} requisições/dia ({req_pct}%)",
            "daily_requests_str": f"{daily_requests} de {FREE_TIER_MAX_RPD} requisições hoje",
            "description": "O Google AI Studio oferece 1.500 requisições diárias e 1 milhão de tokens por minuto gratuitamente."
        }

    formatted_budget = "Ilimitado" if (plan_tier == "paid_tier" and (not budget or budget <= 0)) else format_number(budget)

    return {
        "plan_tier": plan_tier,
        "tier_info": tier_info,
        "daily_budget": budget,
        "daily_used": daily_used,
        "daily_requests": daily_requests,
        "daily_prompt": daily_prompt,
        "daily_output": daily_output,
        "daily_cost_usd": round(daily_cost_usd, 4),
        "daily_cost_brl": round(daily_cost_usd * USD_TO_BRL, 2),
        "weekly_used": weekly_used,
        "weekly_cost_usd": round(weekly_cost_usd, 4),
        "weekly_cost_brl": round(weekly_cost_usd * USD_TO_BRL, 2),
        "weekly_requests": weekly_requests,
        "total_all_time": total_all_time,
        "total_cost_usd": round(total_cost_usd, 4),
        "total_cost_brl": round(total_cost_usd * USD_TO_BRL, 2),
        "percent_used": real_pct,
        "is_exceeded": is_exceeded,
        "safety_lock": safety_lock,
        "remaining_tokens": max(0, budget - daily_used) if (budget and budget > 0) else None,
        "formatted_daily": format_number(daily_used),
        "formatted_weekly": format_number(weekly_used),
        "formatted_budget": formatted_budget,
        "formatted_total": format_number(total_all_time),
        "recent_records": recent_records
    }

def set_daily_budget(budget: int):
    with _lock:
        data = _load_data()
        data["daily_budget"] = budget
        _save_data(data)

def set_safety_lock(enabled: bool):
    with _lock:
        data = _load_data()
        data["safety_lock"] = bool(enabled)
        _save_data(data)

def is_budget_exceeded() -> bool:
    """Verifica se o teto de tokens foi ultrapassado hoje (usado para pausar estudos se a trava estiver ativa)."""
    with _lock:
        data = _load_data()
    if not data.get("safety_lock", False):
        return False
    budget = data.get("daily_budget", DEFAULT_DAILY_BUDGET)
    if budget <= 0:
        return False
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    daily_used = 0
    for rec in data.get("records", []):
        try:
            ts = datetime.fromisoformat(rec.get("timestamp"))
            if ts >= today_start:
                daily_used += rec.get("total_tokens", 0)
        except Exception:
            continue
    return daily_used >= budget

def set_plan_tier(plan_tier: str):
    with _lock:
        data = _load_data()
        data["plan_tier"] = plan_tier
        _save_data(data)

