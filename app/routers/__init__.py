from .auth import router as auth_router
from .users import router as users_router
from .admin import router as admin_router
from .contacts import router as contacts_router
from .cars import router as cars_router
from .books import router as books_router
from .pages import router as pages_router

__all__ = [
    "auth_router",
    "users_router",
    "admin_router",
    "contacts_router",
    "cars_router",
    "books_router",
    "pages_router",
]
