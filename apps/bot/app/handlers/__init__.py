from .admin import router as admin_router
from .casino import router as casino_router
from .help import router as help_router
from .start import router as start_router
from .wallet import router as wallet_router

__all__ = ["admin_router", "casino_router", "help_router", "start_router", "wallet_router"]
