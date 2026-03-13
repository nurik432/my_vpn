from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from database.models import User, Subscription
from services.marzban import MarzbanAPI

router = Router()


def cabinet_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="cabinet")
    kb.button(text="🔑 Мой ключ", callback_data="my_key")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(2, 1)
    return kb.as_markup()


@router.callback_query(F.data == "cabinet")
async def show_cabinet(callback: CallbackQuery, session: AsyncSession, marzban: MarzbanAPI):
    user_id = callback.from_user.id

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.marzban_username:
        await callback.message.edit_text(
            "❌ У тебя пока нет активной подписки.\n\nКупи подписку чтобы начать пользоваться VPN:",
            reply_markup=_no_sub_kb(),
        )
        return

    # Получаем статистику трафика
    try:
        traffic = await marzban.get_user_traffic(user.marzban_username)
        marzban_user = await marzban.get_user(user.marzban_username)
        expire_ts = marzban_user.get("expire")
        expire_str = datetime.fromtimestamp(expire_ts).strftime("%d.%m.%Y") if expire_ts else "∞"
        status = marzban_user.get("status", "unknown")
        status_icon = "✅" if status == "active" else "❌"
    except Exception:
        traffic = {"used_gb": 0, "total_gb": 0, "remaining_gb": 0}
        expire_str = "—"
        status_icon = "❓"

    # Активная подписка
    sub_result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.is_active == True)
        .order_by(Subscription.expires_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    plan_name = sub.plan.upper() if sub else "—"

    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"📋 Имя: <b>{callback.from_user.full_name}</b>\n"
        f"📦 Тариф: <b>{plan_name}</b>\n"
        f"🔌 Статус: {status_icon}\n"
        f"📅 Истекает: <b>{expire_str}</b>\n\n"
        f"📊 <b>Трафик</b>\n"
        f"├ Использовано: <b>{traffic['used_gb']} GB</b>\n"
        f"├ Всего: <b>{traffic['total_gb']} GB</b>\n"
        f"└ Осталось: <b>{traffic['remaining_gb']} GB</b>\n\n"
        f"👥 Рефералов приглашено: <b>{user.referral_count}</b>\n"
        f"🎁 Бонусных дней: <b>{user.referral_bonus_days}</b>"
    )

    await callback.message.edit_text(text, reply_markup=cabinet_kb(), parse_mode="HTML")


@router.callback_query(F.data == "my_key")
async def show_key(callback: CallbackQuery, session: AsyncSession, marzban: MarzbanAPI):
    result = await session.execute(select(User).where(User.id == callback.from_user.id))
    user = result.scalar_one_or_none()

    if not user or not user.marzban_username:
        await callback.answer("❌ У тебя нет активной подписки", show_alert=True)
        return

    try:
        links = await marzban.get_user_links(user.marzban_username)
        if not links:
            await callback.answer("❌ Ключи не найдены", show_alert=True)
            return

        link = links[0]
        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ Назад", callback_data="cabinet")

        await callback.message.edit_text(
            f"🔑 <b>Твой VPN ключ</b>\n\n"
            f"<code>{link}</code>\n\n"
            f"📱 Скопируй и вставь в:\n"
            f"• Android: <b>v2rayNG</b>\n"
            f"• iPhone: <b>Streisand</b> / <b>FoXray</b>\n"
            f"• Windows: <b>v2rayN</b>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.answer("❌ Ошибка получения ключа", show_alert=True)


def _no_sub_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Купить подписку", callback_data="buy")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()