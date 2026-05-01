from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

class MenuMiddleware(BaseMiddleware):
    """
    Middleware to ensure main menu buttons always work by clearing the FSM state
    if a main menu button is pressed.
    """
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if not event.text:
            return await handler(event, data)

        # List of main menu button texts (Comprehensive from MAIN_MENU_BUTTONS)
        main_menu_buttons = [
            "👤 Hisobim", "📚 Kurs ishi", "🎯 Taqdimot", "📄 Maqola", "📌 Tezis",
            "📝 Mustaqil ish", "🎓 Diplom ishi", "🔬 Dissertatsiya", "📖 O'quv qo'llanma",
            "📝 Imtihonga yordam", "💳 To'lov", "💎 VIP Obuna", "🎁 Taklifnoma", 
            "🛠 Admin Panel", "💬 Adminga murojaat", "📝 Narxlar", "❓ Yordam"
        ]

        if event.text in main_menu_buttons:
            state: FSMContext = data.get("state")
            if state:
                current_state = await state.get_state()
                if current_state:
                    # If we are in some state, clear it to allow menu button handlers to trigger
                    await state.clear()
        
        return await handler(event, data)
