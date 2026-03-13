from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User

router = Router()


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Личный кабинет", callback_data="cabinet")
    kb.button(text="🔑 Мой VPN ключ", callback_data="my_key")
    kb.button(text="💳 Купить подписку", callback_data="buy")
    kb.button(text="👥 Рефералы", callback_data="referral")
    kb.adjust(2, 2)
    return kb.as_markup()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    args = message.text.split()
    referrer_id = None

    # Проверяем реф. ссылку
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].replace("ref_", ""))
            if referrer_id == user_id:
                referrer_id = None
        except ValueError:
            referrer_id = None

    # Находим или создаём юзера
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=user_id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            referrer_id=referrer_id,
        )
        session.add(user)

        # Начисляем реферальный бонус пригласившему
        if referrer_id:
            ref_result = await session.execute(select(User).where(User.id == referrer_id))
            referrer = ref_result.scalar_one_or_none()
            if referrer:
                referrer.referral_count += 1
                referrer.referral_bonus_days += 7  # 7 дней за каждого реферала

        await session.commit()
        is_new = True
    else:
        is_new = False

    if is_new:
        text = (
            f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
            f"Добро пожаловать в VPN сервис.\n"
            f"Быстрое подключение по всему миру 🌍\n\n"
            f"Выбери что тебя интересует:"
        )
    else:
        text = (
            f"👋 С возвращением, <b>{message.from_user.first_name}</b>!\n\n"
            f"Выбери что тебя интересует:"
        )

    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "main_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        f"👋 Привет, <b>{callback.from_user.first_name}</b>!\n\nВыбери что тебя интересует:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )