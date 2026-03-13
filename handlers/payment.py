from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice,
    PreCheckoutQuery, SuccessfulPayment
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from database.models import User, Subscription, Payment
from services.marzban import MarzbanAPI

router = Router()

PLANS = {
    "basic_1m": {"name": "Basic 1 месяц", "days": 30, "gb": 50, "stars": 150},
    "basic_3m": {"name": "Basic 3 месяца", "days": 90, "gb": 50, "stars": 350},
    "premium_1m": {"name": "Premium 1 месяц", "days": 30, "gb": 200, "stars": 300},
    "premium_3m": {"name": "Premium 3 месяца", "days": 90, "gb": 200, "stars": 700},
}


def plans_kb():
    kb = InlineKeyboardBuilder()
    for plan_id, plan in PLANS.items():
        kb.button(
            text=f"{plan['name']} — ⭐ {plan['stars']}",
            callback_data=f"buy_{plan_id}",
        )
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "buy")
async def show_plans(callback: CallbackQuery):
    text = (
        "💳 <b>Выбери тариф</b>\n\n"
        "🔹 <b>Basic</b> — 50 GB в месяц\n"
        "🔸 <b>Premium</b> — 200 GB в месяц\n\n"
        "Оплата через Telegram Stars ⭐"
    )
    await callback.message.edit_text(text, reply_markup=plans_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery):
    plan_id = callback.data.replace("buy_", "")
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден")
        return

    await callback.message.answer_invoice(
        title=plan["name"],
        description=f"VPN подписка на {plan['days']} дней, {plan['gb']} GB трафика",
        payload=plan_id,
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, session: AsyncSession, marzban: MarzbanAPI):
    payment: SuccessfulPayment = message.successful_payment
    plan_id = payment.invoice_payload
    plan = PLANS.get(plan_id)
    user_id = message.from_user.id

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    # Создаём юзера в Marzban если нет
    if not user.marzban_username:
        marzban_username = f"tg_{user_id}"
        await marzban.create_user(marzban_username, data_limit_gb=plan["gb"], expire_days=plan["days"])
        user.marzban_username = marzban_username
    else:
        # Продлеваем подписку
        await marzban.extend_user(user.marzban_username, expire_days=plan["days"])

    # Сохраняем подписку
    sub = Subscription(
        user_id=user_id,
        plan=plan_id,
        days=plan["days"],
        data_limit_gb=plan["gb"],
        expires_at=datetime.now() + timedelta(days=plan["days"]),
    )
    session.add(sub)

    # Сохраняем платёж
    payment_record = Payment(
        user_id=user_id,
        amount=plan["stars"],
        currency="XTR",
        plan=plan_id,
        status="paid",
        telegram_payment_id=payment.telegram_payment_charge_id,
    )
    session.add(payment_record)

    # Применяем бонусные дни за рефералов
    if user.referral_bonus_days > 0:
        await marzban.extend_user(user.marzban_username, expire_days=user.referral_bonus_days)
        user.referral_bonus_days = 0

    await session.commit()

    kb = InlineKeyboardBuilder()
    kb.button(text="🔑 Получить ключ", callback_data="my_key")
    kb.button(text="👤 Личный кабинет", callback_data="cabinet")
    kb.adjust(1)

    await message.answer(
        f"✅ <b>Оплата прошла успешно!</b>\n\n"
        f"📦 Тариф: <b>{plan['name']}</b>\n"
        f"📅 Срок: <b>{plan['days']} дней</b>\n"
        f"📊 Трафик: <b>{plan['gb']} GB</b>\n\n"
        f"Нажми кнопку ниже чтобы получить VPN ключ 👇",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )