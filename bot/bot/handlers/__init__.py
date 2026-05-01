from aiogram import Router
from aiogram.filters import CommandStart
from .modules import menu, orders, payments, admin, support, payments_flow, feedback

router = Router()

# /start MUST be on the parent router — parent handlers run BEFORE child routers,
# so /start always works regardless of which wizard state the user is in.
router.message.register(menu.cmd_start, CommandStart())

# Critical & restricted
router.include_router(admin.router)

# Core flows
router.include_router(payments.router)
router.include_router(payments_flow.router)
router.include_router(orders.router)

# User interaction
router.include_router(feedback.router)
router.include_router(support.router)
router.include_router(menu.router)  # fallback / main menu
