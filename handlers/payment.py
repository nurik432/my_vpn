import uuid
import os
import aiohttp

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from database.models import User, Subscription, Payment

router = Router()

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")

PLANS = {
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


# ─── Клавиатуры ───────────────────────────────────────────────────────────────

def plans_kb(show_trial: bool = False):
    kb = InlineKeyboardBuilder()
    if show_trial:
        kb.button(text="🎁 Попробовать бесплатно (3 дня)", callback_data="buy_trial")
    for plan_id, plan in PLANS.items():
        if plan_id == "trial":
            continue
        kb.button(
            text=f"{plan['emoji']} {plan['name']} — {plan['description']}",
            callback_data=f"plan_{plan_id}",
        )
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


def payment_method_kb(plan_id: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Картой (ЮKassa)", callback_data=f"pay_yoo_{plan_id}")
    kb.button(text="₿ Криптой (CryptoBot)", callback_data=f"pay_crypto_{plan_id}")
    kb.button(text="◀️ Назад", callback_data="buy")
    kb.adjust(1)
    return kb.as_markup()


# ─── YooKassa ─────────────────────────────────────────────────────────────────

async def create_yookassa_payment(amount: int, plan_id: str, user_id: int) -> dict:
    payment_uuid = str(uuid.uuid4())
    payload = {
        "amount": {"value": f"{amount}.00", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{BOT_USERNAME}",
        },
        "capture": True,
        "description": f"VPN — {PLANS[plan_id]['name']}",
        "metadata": {"user_id": str(user_id), "plan_id": plan_id, "method": "yookassa"},
    }
    auth = aiohttp.BasicAuth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
    headers = {"Idempotence-Key": payment_uuid, "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.yookassa.ru/v3/payments",
            json=payload, auth=auth, headers=headers,
        ) as resp:
            return await resp.json()


async def check_yookassa_payment(payment_id: str) -> dict:
    auth = aiohttp.BasicAuth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.yookassa.ru/v3/payments/{payment_id}", auth=auth
        ) as resp:
            return await resp.json()


# ─── CryptoBot ────────────────────────────────────────────────────────────────

async def create_cryptobot_invoice(amount: float, plan_id: str, user_id: int) -> dict:
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"VPN — {PLANS[plan_id]['name']}",
        "payload": f"{user_id}:{plan_id}",
        "expires_in": 3600,  # 1 час на оплату
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://pay.crypt.bot/api/createInvoice",
            json=payload, headers=headers,
        ) as resp:
            return await resp.json()


async def check_cryptobot_invoice(invoice_id: int) -> dict:
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}",
            headers=headers,
        ) as resp:
            data = await resp.json()
            items = data.get("result", {}).get("items", [])
            return items[0] if items else {}


# ─── Хендлеры ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "buy")
async def show_plans(callback: CallbackQuery, session: AsyncSession):
    result = await session.execute(select(User).where(User.id == callback.from_user.id))
    user = result.scalar_one_or_none()
    show_trial = not user.trial_used if user else True

    await callback.message.edit_text(
        "💳 <b>Выбери тариф</b>\n\n"
        "🔐 Безлимитный трафик\n"
        "🌍 Все регионы включены\n"
        "⚡️ Высокая скорость\n\n"
        "Оплата картой или криптовалютой",
        reply_markup=plans_kb(show_trial),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("plan_"))
async def choose_payment_method(callback: CallbackQuery):
    plan_id = callback.data.replace("plan_", "")
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден")
        return

    await callback.message.edit_text(
        f"{plan['emoji']} <b>{plan['name']}</b>\n\n"
        f"💳 Картой: <b>{plan['price_rub']} ₽</b>\n"
        f"₿ Криптой: <b>{plan['price_usdt']} USDT</b>\n\n"
        f"Выбери способ оплаты:",
        reply_markup=payment_method_kb(plan_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "buy_trial")
async def activate_trial(callback: CallbackQuery, session: AsyncSession, marzban):
    user_id = callback.from_user.id
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user.trial_used:
        await callback.answer("❌ Пробный период уже использован", show_alert=True)
        return

    plan = PLANS["trial"]
    if not user.marzban_username:
        marzban_username = f"tg_{user_id}"
        await marzban.create_user(marzban_username, data_limit_gb=100, expire_days=plan["days"])
        user.marzban_username = marzban_username
    else:
        await marzban.extend_user(user.marzban_username, expire_days=plan["days"])

    user.trial_used = True
    session.add(Subscription(
        user_id=user_id, plan="trial", days=plan["days"], data_limit_gb=100,
        expires_at=datetime.now() + timedelta(days=plan["days"]),
    ))
    await session.commit()

    kb = InlineKeyboardBuilder()
    kb.button(text="🔑 Получить VPN ключ", callback_data="my_key")
    kb.button(text="💳 Купить подписку", callback_data="buy")
    kb.adjust(1)

    await callback.message.edit_text(
        "🎁 <b>Пробный период активирован!</b>\n\n"
        "У тебя есть <b>3 дня</b> бесплатного VPN.\n"
        "Нажми кнопку ниже чтобы получить ключ 👇",
        reply_markup=kb.as_markup(), parse_mode="HTML",
    )


# ─── ЮKassa оплата ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay_yoo_"))
async def pay_yookassa(callback: CallbackQuery, session: AsyncSession):
    plan_id = callback.data.replace("pay_yoo_", "")
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден")
        return

    try:
        payment = await create_yookassa_payment(plan["price_rub"], plan_id, callback.from_user.id)
        payment_url = payment["confirmation"]["confirmation_url"]
        payment_id = payment["id"]

        session.add(Payment(
            user_id=callback.from_user.id, amount=plan["price_rub"],
            currency="RUB", plan=plan_id, status="pending",
            telegram_payment_id=payment_id,
        ))
        await session.commit()

        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Оплатить", url=payment_url)
        kb.button(text="✅ Я оплатил", callback_data=f"check_yoo_{payment_id}")
        kb.button(text="◀️ Назад", callback_data=f"plan_{plan_id}")
        kb.adjust(1)

        await callback.message.edit_text(
            f"💳 <b>Оплата картой — {plan['name']}</b>\n\n"
            f"Сумма: <b>{plan['price_rub']} ₽</b>\n\n"
            f"1. Нажми <b>«Оплатить»</b>\n"
            f"2. Оплати картой на сайте ЮKassa\n"
            f"3. Вернись и нажми <b>«Я оплатил»</b>",
            reply_markup=kb.as_markup(), parse_mode="HTML",
        )
    except Exception:
        await callback.answer("❌ Ошибка создания платежа. Попробуй позже.", show_alert=True)


@router.callback_query(F.data.startswith("check_yoo_"))
async def check_yoo(callback: CallbackQuery, session: AsyncSession, marzban):
    payment_id = callback.data.replace("check_yoo_", "")
    try:
        data = await check_yookassa_payment(payment_id)
        if data.get("status") != "succeeded":
            await callback.answer("⏳ Оплата ещё не поступила. Подожди и попробуй снова.", show_alert=True)
            return
        await _activate_subscription(callback, session, marzban, payment_id, data["metadata"]["plan_id"], "RUB")
    except Exception:
        await callback.answer("❌ Ошибка проверки. Попробуй позже.", show_alert=True)


# ─── CryptoBot оплата ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(callback: CallbackQuery, session: AsyncSession):
    plan_id = callback.data.replace("pay_crypto_", "")
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден")
        return

    try:
        invoice = await create_cryptobot_invoice(plan["price_usdt"], plan_id, callback.from_user.id)
        invoice_data = invoice.get("result", {})
        pay_url = invoice_data.get("pay_url", "")
        invoice_id = str(invoice_data.get("invoice_id", ""))

        session.add(Payment(
            user_id=callback.from_user.id, amount=int(plan["price_usdt"] * 100),
            currency="USDT", plan=plan_id, status="pending",
            telegram_payment_id=invoice_id,
        ))
        await session.commit()

        kb = InlineKeyboardBuilder()
        kb.button(text="₿ Оплатить криптой", url=pay_url)
        kb.button(text="✅ Я оплатил", callback_data=f"check_crypto_{invoice_id}")
        kb.button(text="◀️ Назад", callback_data=f"plan_{plan_id}")
        kb.adjust(1)

        await callback.message.edit_text(
            f"₿ <b>Оплата криптой — {plan['name']}</b>\n\n"
            f"Сумма: <b>{plan['price_usdt']} USDT</b>\n\n"
            f"1. Нажми <b>«Оплатить криптой»</b>\n"
            f"2. Оплати в @CryptoBot\n"
            f"3. Вернись и нажми <b>«Я оплатил»</b>",
            reply_markup=kb.as_markup(), parse_mode="HTML",
        )
    except Exception:
        await callback.answer("❌ Ошибка создания счёта. Попробуй позже.", show_alert=True)


@router.callback_query(F.data.startswith("check_crypto_"))
async def check_crypto(callback: CallbackQuery, session: AsyncSession, marzban):
    invoice_id = callback.data.replace("check_crypto_", "")
    try:
        data = await check_cryptobot_invoice(int(invoice_id))
        if data.get("status") != "paid":
            await callback.answer("⏳ Оплата ещё не поступила. Подожди и попробуй снова.", show_alert=True)
            return
        plan_id = data.get("payload", ":").split(":")[1]
        await _activate_subscription(callback, session, marzban, invoice_id, plan_id, "USDT")
    except Exception:
        await callback.answer("❌ Ошибка проверки. Попробуй позже.", show_alert=True)


# ─── Общая активация подписки ─────────────────────────────────────────────────

async def _activate_subscription(callback, session, marzban, payment_id: str, plan_id: str, currency: str):
    user_id = callback.from_user.id

    # Проверяем дубликат
    dup = await session.execute(
        select(Payment).where(Payment.telegram_payment_id == payment_id, Payment.status == "paid")
    )
    if dup.scalar_one_or_none():
        await callback.answer("✅ Платёж уже обработан", show_alert=True)
        return

    plan = PLANS[plan_id]

    # Обновляем статус платежа
    pay_res = await session.execute(select(Payment).where(Payment.telegram_payment_id == payment_id))
    pay_rec = pay_res.scalar_one_or_none()
    if pay_rec:
        pay_rec.status = "paid"

    # Получаем юзера
    user_res = await session.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()

    # Создаём или продлеваем в Marzban
    if not user.marzban_username:
        marzban_username = f"tg_{user_id}"
        await marzban.create_user(marzban_username, data_limit_gb=100, expire_days=plan["days"])
        user.marzban_username = marzban_username
    else:
        await marzban.extend_user(user.marzban_username, expire_days=plan["days"])

    session.add(Subscription(
        user_id=user_id, plan=plan_id, days=plan["days"], data_limit_gb=100,
        expires_at=datetime.now() + timedelta(days=plan["days"]),
    ))

    # Бонусные дни за рефералов
    if user.referral_bonus_days > 0:
        await marzban.extend_user(user.marzban_username, expire_days=user.referral_bonus_days)
        user.referral_bonus_days = 0

    await session.commit()

    kb = InlineKeyboardBuilder()
    kb.button(text="🔑 Получить VPN ключ", callback_data="my_key")
    kb.button(text="👤 Личный кабинет", callback_data="cabinet")
    kb.adjust(1)

    currency_icon = "₽" if currency == "RUB" else "USDT"
    amount = plan["price_rub"] if currency == "RUB" else plan["price_usdt"]

    await callback.message.edit_text(
        f"✅ <b>Оплата прошла успешно!</b>\n\n"
        f"📦 Тариф: <b>{plan['name']}</b>\n"
        f"💰 Сумма: <b>{amount} {currency_icon}</b>\n"
        f"📅 Срок: <b>{plan['days']} дней</b>\n\n"
        f"Нажми кнопку ниже чтобы получить VPN ключ 👇",
        reply_markup=kb.as_markup(), parse_mode="HTML",
    )