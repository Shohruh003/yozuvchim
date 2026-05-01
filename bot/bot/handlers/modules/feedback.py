from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import DB, AsyncSessionLocal, logger

router = Router(name="feedback_handlers")

@router.callback_query(F.data.startswith("feed:"))
async def feedback_handler(callback: CallbackQuery):
    """
    Handles callbacks from feedback keyboard: feed:{req_id}:{rating}
    """
    try:
        parts = callback.data.split(":")
        if len(parts) != 3:
            return
        
        req_id = int(parts[1])
        rating = int(parts[2])
        
        async with AsyncSessionLocal() as session:
            db_req = await DB.get_request(session, req_id)
            if db_req:
                db_req.rating = rating
                await session.commit()
                
                # Acknowledge the feedback
                response_text = {
                    1: "😔 Rahmat, xatolarimiz ustida ishlaymiz.",
                    2: "😐 Rahmat, sifatni yaxshilashga harakat qilamiz.",
                    3: "🙂 Rahmat, yanada yaxshilashda davom etamiz.",
                    4: "😊 Rahmat, biz xursandmiz!",
                    5: "🤩 Katta rahmat! Sizga yoqqanidan mamnunmiz!",
                }.get(rating, "Rahmat!")
                
                await callback.answer(response_text, show_alert=True)
                
                # Remove keyboard after feedback
                await callback.message.edit_reply_markup(reply_markup=None)
                
                logger.info(f"User {callback.from_user.id} rated request #{req_id} as {rating} stars.")
            else:
                await callback.answer("Request not found.")
                
    except Exception as e:
        logger.error(f"Feedback handler error: {e}")
        await callback.answer("Xatolik yuz berdi.")
