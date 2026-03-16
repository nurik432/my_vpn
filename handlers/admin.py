import os
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

from handlers.payment import PLANS


class EditPlan(StatesGroup):
    entering_value = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Управление тарифами", callback_data="admin_plans")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    kb.adjust(1)
    return kb.as_markup()


def plans_list_kb():
    kb = InlineKeyboardBuilder()
    for plan_id, plan in PLANS.items():
        if plan_id == "trial":
            kb.button(text=f"{plan['emoji']} {plan['name']} (бесплатно)", callback_data=f"admin_edit|{plan_id}")
        else:
            kb.button(
                text=f"{plan['emoji']} {plan['name']} — {plan['price_rub']}₽ / ${plan['price_usdt']}",
                callback_data=f"admin_edit|{plan_id}",
            )
    kb.button(text="◀️ Назад", callback_data="admin_menu")
    kb.adjust(1)
    return kb.as_markup()


def plan_fields_kb(plan_id: str):
    kb = InlineKeyboardBuilder()
    plan = PLANS[plan_id]
    kb.button(text=f"📅 Дней: {plan['days']}", callback_data=f"admin_field|{plan_id}|days")
    if plan_id != "trial":
        kb.button(text=f"💳 Цена ₽: {plan['price_rub']}", callback_data=f"admin_field|{plan_id}|price_rub")
        kb.button(text=f"₿ Цена USDT: {plan['price_usdt']}", callback_data=f"admin_field|{plan_id}|price_usdt")
    kb.button(text=f"📝 Название: {plan['name']}", callback_data=f"admin_field|{plan_id}|name")
    kb.button(text="◀️ Назад", callback_data="admin_plans")
    kb.adjust(1)
    return kb.as_markup()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return
    await message.answer("👑 <b>Админ панель</b>\n\nВыбери раздел:", reply_markup=admin_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("👑 <b>Админ панель</b>\n\nВыбери раздел:", reply_markup=admin_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin_plans")
async def admin_plans(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("💰 <b>Управление тарифами</b>\n\nВыбери тариф:", reply_markup=plans_list_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_edit|"))
async def admin_edit_plan(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    plan_id = callback.data.split("|")[1]
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден")
        return

    text = f"{plan['emoji']} <b>{plan['name']}</b>\n\n📅 Дней: <b>{plan['days']}</b>\n"
    if plan_id != "trial":
        text += f"💳 Цена ₽: <b>{plan['price_rub']}</b>\n₿ Цена USDT: <b>{plan['price_usdt']}</b>\n"
    text += "\nВыбери что изменить:"

    await callback.message.edit_text(text, reply_markup=plan_fields_kb(plan_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_field|"))
async def admin_field(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    _, plan_id, field = callback.data.split("|")

    field_names = {
        "days": "количество дней",
        "price_rub": "цену в рублях",
        "price_usdt": "цену в USDT",
        "name": "название тарифа",
    }

    await state.set_state(EditPlan.entering_value)
    await state.update_data(plan_id=plan_id, field=field)

    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data=f"admin_edit|{plan_id}")

    await callback.message.edit_text(
        f"✏️ Введи новое значение для <b>{field_names.get(field, field)}</b>\n\n"
        f"Текущее значение: <b>{PLANS[plan_id][field]}</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )


@router.message(EditPlan.entering_value)
async def process_new_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    plan_id = data["plan_id"]
    field = data["field"]
    new_value_raw = message.text.strip()

    try:
        if field in ("days", "price_rub"):
            new_value = int(new_value_raw)
        elif field == "price_usdt":
            new_value = float(new_value_raw)
        else:
            new_value = new_value_raw

        old_value = PLANS[plan_id][field]
        PLANS[plan_id][field] = new_value
        await state.clear()

        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ К тарифу", callback_data=f"admin_edit|{plan_id}")
        kb.button(text="📋 Все тарифы", callback_data="admin_plans")
        kb.adjust(1)

        await message.answer(
            f"✅ <b>Обновлено!</b>\n\n"
            f"Тариф: <b>{PLANS[plan_id]['name']}</b>\n"
            f"Поле: <b>{field}</b>\n"
            f"Было: <b>{old_value}</b>\n"
            f"Стало: <b>{new_value}</b>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )
    except ValueError:
        kb = InlineKeyboardBuilder()
        kb.button(text="❌ Отмена", callback_data=f"admin_edit|{plan_id}")
        await message.answer("❌ Неверный формат. Введи число.", reply_markup=kb.as_markup())


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery, session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    from sqlalchemy import select, func
    from database.models import User, Payment, Subscription

    users_count = await session.scalar(select(func.count(User.id)))
    paid_count = await session.scalar(select(func.count(Payment.id)).where(Payment.status == "paid"))
    revenue_rub = await session.scalar(
        select(func.sum(Payment.amount)).where(Payment.status == "paid", Payment.currency == "RUB")
    ) or 0
    active_subs = await session.scalar(select(func.count(Subscription.id)).where(Subscription.is_active == True))

    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Назад", callback_data="admin_menu")

    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{users_count}</b>\n"
        f"💳 Успешных платежей: <b>{paid_count}</b>\n"
        f"💰 Выручка (₽): <b>{revenue_rub} ₽</b>\n"
        f"🔐 Активных подписок: <b>{active_subs}</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )