import os
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]


class SupportState(StatesGroup):
    waiting_message = State()


@router.callback_query(F.data == "support")
async def show_support(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.waiting_message)

    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="cancel_support")
    kb.adjust(1)

    await callback.message.edit_text(
        "💬 <b>Поддержка</b>\n\n"
        "Опиши свою проблему и мы поможем.\n"
        "Напиши сообщение — оно придёт администратору:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cancel_support")
async def cancel_support(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ В главное меню", callback_data="main_menu")
    await callback.message.edit_text(
        "❌ Обращение отменено.",
        reply_markup=kb.as_markup(),
    )


@router.message(SupportState.waiting_message)
async def handle_support_message(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user

    # Отправляем заявку всем админам
    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardBuilder()
            kb.button(text="💬 Ответить", url=f"tg://user?id={user.id}")
            await message.bot.send_message(
                admin_id,
                f"📩 <b>Новая заявка в поддержку</b>\n\n"
                f"👤 Пользователь: <a href='tg://user?id={user.id}'>{user.full_name}</a>\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"📱 Username: @{user.username or '—'}\n\n"
                f"💬 <b>Сообщение:</b>\n{message.text}",
                reply_markup=kb.as_markup(),
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")

    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ В главное меню", callback_data="main_menu")

    await message.answer(
        "✅ <b>Заявка отправлена!</b>\n\n"
        "Администратор свяжется с вами в ближайшее время.",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )