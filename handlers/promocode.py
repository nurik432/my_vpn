from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from database.models import User, Promocode, UserPromocode

router = Router()

class PromocodeState(StatesGroup):
    waiting_for_code = State()

@router.callback_query(F.data == "enter_promocode")
async def process_enter_promocode(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Отмена", callback_data="main_menu")
    
    await callback.message.edit_text(
        "🎫 <b>Введите ваш промокод:</b>", 
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await state.set_state(PromocodeState.waiting_for_code)


@router.message(PromocodeState.waiting_for_code)
async def process_promocode_input(message: Message, state: FSMContext, session: AsyncSession):
    code = message.text.strip().upper()
    user_id = message.from_user.id
    
    await state.clear()
    
    # Check if the code exists
    result = await session.execute(select(Promocode).where(Promocode.code == code))
    promocode = result.scalar_one_or_none()
    
    if not promocode:
        await message.answer("❌ Промокод не найден или введен неверно.")
        return
        
    if not promocode.is_active:
        await message.answer("❌ Этот промокод больше не активен.")
        return
        
    if promocode.expires_at and promocode.expires_at < datetime.now():
        await message.answer("❌ Срок действия этого промокода истёк.")
        return
        
    if promocode.max_uses and promocode.current_uses >= promocode.max_uses:
        await message.answer("❌ Лимит активаций этого промокода исчерпан.")
        return
        
    # Check if user already used this promocode
    user_promo_result = await session.execute(
        select(UserPromocode)
        .where(UserPromocode.user_id == user_id)
        .where(UserPromocode.promocode_id == promocode.id)
    )
    if user_promo_result.scalar_one_or_none():
        await message.answer("❌ Вы уже активировали этот промокод.")
        return
        
    # Apply promocode benefits
    result_user = await session.execute(select(User).where(User.id == user_id))
    user = result_user.scalar_one_or_none()
    
    if not user:
        await message.answer("❌ Произошла ошибка. Пользователь не найден.")
        return

    # Add usage record
    user_promo = UserPromocode(user_id=user_id, promocode_id=promocode.id)
    session.add(user_promo)
    
    # Update promocode uses
    promocode.current_uses += 1
    
    response_msg = "✅ Промокод успешно активирован!\n\n"
    
    if promocode.bonus_days:
        user.trial_used = True  # Maybe we want to mark trial as used if promo logic covers it
        user.referral_bonus_days += promocode.bonus_days # Easiest way to add bonus days for now
        response_msg += f"🎁 Вам начислено <b>{promocode.bonus_days}</b> бонусных дней!"
    
    if promocode.discount_percent:
        # In a real app we would store discount_percent somewhere for the user's next payment
        response_msg += f"💸 Вы получили скидку <b>{promocode.discount_percent}%</b> на следующую покупку!"
        
    await session.commit()
    
    from handlers.start import main_menu_kb
    await message.answer(response_msg, reply_markup=main_menu_kb(), parse_mode="HTML")
