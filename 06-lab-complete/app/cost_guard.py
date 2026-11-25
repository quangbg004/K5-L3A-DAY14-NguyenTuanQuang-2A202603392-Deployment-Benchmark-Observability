from datetime import datetime, timezone

from fastapi import HTTPException

from .config import settings
from .redis_client import r


# Mock prices in USD per 1,000 tokens.
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006
COST_RETENTION_SECONDS = 2 * 24 * 60 * 60


def _today_cost_key() -> str:
    return f"agent:cost:{datetime.now(timezone.utc).date().isoformat()}"


def check_budget() -> None:
    spent = float(r.get(_today_cost_key()) or 0)
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    key = _today_cost_key()
    with r.pipeline() as transaction:
        transaction.incrbyfloat(key, cost)
        transaction.expire(key, COST_RETENTION_SECONDS)
        transaction.execute()
    return cost
