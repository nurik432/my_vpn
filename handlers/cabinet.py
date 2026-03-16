from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from database.models import User, Subscription

router = Router()


def cabinet_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="cabinet")
    kb.button(text="🔑 Мой ключ", callback_data="my_key")
    kb.button(text="♻️ Новый ключ", callback_data="reset_key")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def confirm_reset_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, пересоздать", callback_data="confirm_reset_key")
    kb.button(text="❌ Отмена", callback_data="cabinet")
    kb.adjust(1)
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
        if expire_ts and int(expire_ts) > 0:
            from datetime import datetime
            expire_str = datetime.fromtimestamp(int(expire_ts)).strftime("%d.%m.%Y")
        else:
            expire_str = "Не ограничено"
        status = marzban_user.get("status", "unknown")
        status_icon = "✅ Активна" if status == "active" else "❌ Неактивна"
    except Exception as e:
        print(f"Marzban error for {user.marzban_username}: {e}")
        traffic = {"used_gb": 0, "unlimited": True}
        expire_str = "—"
        status_icon = "❓ Неизвестно"

    # Активная подписка
    sub_result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.is_active == True)
        .order_by(Subscription.expires_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    plan_name = sub.plan.upper() if sub else "—"

    traffic_text = (
        f"├ Использовано: <b>{traffic['used_gb']} GB</b>\n"
        f"└ Лимит: <b>{'Безлимит ∞' if traffic.get('unlimited', True) else str(traffic.get('total_gb', 0)) + ' GB'}</b>"
    )

    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"📋 Имя: <b>{callback.from_user.full_name}</b>\n"
        f"📦 Тариф: <b>{plan_name}</b>\n"
        f"🔌 Статус: {status_icon}\n"
        f"📅 Истекает: <b>{expire_str}</b>\n\n"
        f"📊 <b>Трафик</b>\n"
        f"{traffic_text}\n\n"
        f"👥 Рефералов приглашено: <b>{user.referral_count}</b>\n"
        f"🎁 Бонусных дней: <b>{user.referral_bonus_days}</b>"
    )

    try:
        await callback.message.edit_text(text, reply_markup=cabinet_kb(), parse_mode="HTML")
    except TelegramBadRequest:
        await callback.answer("✅ Данные актуальны")


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
        kb.button(text="♻️ Новый ключ", callback_data="reset_key")
        kb.button(text="◀️ Назад", callback_data="cabinet")
        kb.adjust(1)

        await callback.message.edit_text(
            f"🔑 <b>Твой VPN ключ</b>\n\n"
            f"<code>{link}</code>\n\n"
            f"📱 Скопируй и вставь в:\n"
            f"• Android: <b>v2rayNG</b>\n"
            f"• iPhone: <b>Streisand</b> / <b>FoXray</b>\n"
            f"• Windows: <b>v2rayN</b>\n\n"
            f"⚠️ Если ключ не работает — нажми <b>«Новый ключ»</b>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        await callback.answer("❌ Ошибка получения ключа", show_alert=True)


@router.callback_query(F.data == "reset_key")
async def reset_key_confirm(callback: CallbackQuery):
    await callback.message.edit_text(
        "♻️ <b>Пересоздать VPN ключ?</b>\n\n"
        "Старый ключ перестанет работать.\n"
        "Тебе нужно будет импортировать новый ключ в приложение.\n\n"
        "Продолжить?",
        reply_markup=confirm_reset_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "confirm_reset_key")
async def confirm_reset_key(callback: CallbackQuery, session: AsyncSession, marzban: MarzbanAPI):
    user_id = callback.from_user.id

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.marzban_username:
        await callback.answer("❌ У тебя нет активной подписки", show_alert=True)
        return

    # Проверяем активную подписку в БД
    from sqlalchemy import select
    sub_result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.is_active == True)
        .order_by(Subscription.expires_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        await callback.answer("❌ Нет активной подписки для пересоздания ключа", show_alert=True)
        return

    await callback.message.edit_text("⏳ Пересоздаю ключ...", parse_mode="HTML")

    try:
        old_username = user.marzban_username
        print(f"Reset key: deleting {old_username}")

        marzban_user = await marzban.get_user(old_username)
        print(f"Got marzban user: {marzban_user}")
        expire_ts = marzban_user.get("expire")

        await marzban.delete_user(old_username)
        print(f"Deleted {old_username}")

        import time
        new_username = f"tg_{user_id}_{int(time.time())}"
        print(f"Creating new user: {new_username}")

        await marzban.create_user_raw(
            username=new_username,
            data_limit=0,
            expire_ts=expire_ts,
        )
        print(f"Created {new_username}")

        # Обновляем username в БД
        user.marzban_username = new_username
        await session.commit()

        # Получаем новый ключ
        links = await marzban.get_user_links(new_username)
        link = links[0] if links else "Ключ не найден"

        kb = InlineKeyboardBuilder()
        kb.button(text="👤 Личный кабинет", callback_data="cabinet")
        kb.adjust(1)

        await callback.message.edit_text(
            f"✅ <b>Новый ключ готов!</b>\n\n"
            f"<code>{link}</code>\n\n"
            f"📱 Импортируй в приложение:\n"
            f"• Android: <b>v2rayNG</b>\n"
            f"• iPhone: <b>Streisand</b> / <b>FoXray</b>\n"
            f"• Windows: <b>v2rayN</b>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    except Exception as e:
        print(f"Reset key error: {e}")
        import traceback
        traceback.print_exc()
        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ Назад", callback_data="cabinet")
        await callback.message.edit_text(
            "❌ <b>Ошибка пересоздания ключа</b>\n\nПопробуй позже или обратись в поддержку.",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )


def _no_sub_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Купить подписку", callback_data="buy")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()