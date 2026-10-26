"""Tüm modelleri tek noktadan import eder.

Alembic autogenerate ve SQLAlchemy mapper'ının tüm tabloları/ilişkileri
görebilmesi için bu modülün import edilmesi yeterlidir.
"""

from app.core.base_model import Base
from app.modules.auth.models import Role, RoleName, User, user_roles
from app.modules.borrowing.models import (
    Borrowing,
    BorrowingStatus,
    Reservation,
    ReservationStatus,
    StockMovement,
)
from app.modules.catalog.models import (
    Author,
    Book,
    Category,
    Publisher,
    book_authors,
    book_categories,
)
from app.modules.admin.models import SystemLog
from app.modules.review.models import Review, ReviewReaction

__all__ = [
    "Base",
    "User", "Role", "RoleName", "user_roles",
    "Publisher", "Category", "Author", "Book", "book_authors", "book_categories",
    "Borrowing", "BorrowingStatus", "Reservation", "ReservationStatus", "StockMovement",
    "Review", "ReviewReaction",
    "SystemLog",
]

