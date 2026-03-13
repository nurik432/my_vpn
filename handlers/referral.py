from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User

router = Router()


@router.callback_query(F.data == "referral")
async def show_referral(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Поделиться ссылкой", switch_inline_query=f"Присоединяйся к VPN сервису! {ref_link}")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1)

    text = (
        f"👥 <b>Реферальная программа</b>\n\n"
        f"Приглашай друзей и получай бонусы!\n\n"
        f"🎁 <b>За каждого приглашённого:</b>\n"
        f"└ +7 дней к подписке бесплатно\n\n"
        f"📊 <b>Твоя статистика:</b>\n"
        f"├ Приглашено: <b>{user.referral_count}</b> чел.\n"
        f"└ Заработано дней: <b>{user.referral_count * 7}</b>\n\n"
        f"🔗 <b>Твоя реф. ссылка:</b>\n"
        f"<code>{ref_link}</code>"
    )

    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")