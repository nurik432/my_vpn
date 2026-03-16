import json
import os

PLANS_FILE = os.getenv("PLANS_FILE", "/app/data/plans.json")

DEFAULT_PLANS = {
    "trial": {
        "name": "Пробный период",
        "days": 3,
        "price_rub": 0,
        "price_usdt": 0,
        "description": "3 дня бесплатно",
        "emoji": "🎁",
    },
    "1m": {
        "name": "1 месяц",
        "days": 30,
        "price_rub": 199,
        "price_usdt": 2.5,
        "description": "199 ₽ / $2.5",
        "emoji": "📅",
    },
    "3m": {
        "name": "3 месяца",
        "days": 90,
        "price_rub": 499,
        "price_usdt": 5.5,
        "description": "499 ₽ / $5.5 — скидка 25%",
        "emoji": "💰",
    },
    "6m": {
        "name": "6 месяцев",
        "days": 180,
        "price_rub": 899,
        "price_usdt": 9.9,
        "description": "899 ₽ / $9.9 — скидка 35%",
        "emoji": "🔥",
    },
    "1y": {
        "name": "1 год",
        "days": 365,
        "price_rub": 1490,
        "price_usdt": 16.9,
        "description": "1490 ₽ / $16.9 — скидка 50%",
        "emoji": "👑",
    },
}


def load_plans() -> dict:
    try:
        if os.path.exists(PLANS_FILE):
            with open(PLANS_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return DEFAULT_PLANS.copy()


def save_plans(plans: dict):
    try:
        os.makedirs(os.path.dirname(PLANS_FILE), exist_ok=True)
        with open(PLANS_FILE, "w") as f:
            json.dump(plans, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving plans: {e}")


def update_plan_field(plan_id: str, field: str, value):
    plans = load_plans()
    if plan_id in plans:
        plans[plan_id][field] = value
        # Обновляем description автоматически
        if field in ("price_rub", "price_usdt") and plan_id != "trial":
            p = plans[plan_id]
            discounts = {"3m": "скидка 25%", "6m": "скидка 35%", "1y": "скидка 50%"}
            discount = discounts.get(plan_id, "")
            desc = f"{p['price_rub']} ₽ / ${p['price_usdt']}"
            if discount:
                desc += f" — {discount}"
            plans[plan_id]["description"] = desc
        save_plans(plans)
    return plans


# Глобальный объект планов — загружается при старте
PLANS = load_plans()