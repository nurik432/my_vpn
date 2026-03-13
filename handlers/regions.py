from aiogram import Router, types

router = Router()

@router.message(lambda m: m.text == "Выбор региона")
async def select_region(message: types.Message):
    await message.answer("Выберите регион для подключения:")
