from datetime import date, datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.admin.schemas import UnpaidPenaltiesResponse, UnpaidPenaltyItem
from app.modules.borrowing.models import Borrowing, BorrowingStatus
from app.modules.borrowing.service import sync_overdue_borrowings


def _to_date(val: date | datetime | None) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    return val


def get_unpaid_penalties(db: Session) -> UnpaidPenaltiesResponse:
    """
    Hem iade edilmiş ama cezası henüz ödenmemiş kayıtları hem de şu an teslim tarihi
    geçmiş aktif (OVERDUE) ödünçlerden doğan güncel borçları döndürür.
    """
    sync_overdue_borrowings(db)
    today = date.today()

    stmt = select(Borrowing).order_by(Borrowing.due_date.asc())
    all_borrowings = db.scalars(stmt).all()

    items: list[UnpaidPenaltyItem] = []
    total_unpaid = 0.0

    for b in all_borrowings:
        penalty = 0.0
        overdue_days = 0

        if b.status == BorrowingStatus.RETURNED:
            # İade edilmiş ama cezası ödenmemiş
            if (b.penalty_amount or 0.0) > 0.0 and not b.is_penalty_paid:
                penalty = float(b.penalty_amount)
                overdue_days = b.overdue_days
                total_unpaid += penalty
                items.append(
                    UnpaidPenaltyItem(
                        borrowing_id=b.id,
                        user_id=b.user_id,
                        user_full_name=f"{b.user.first_name} {b.user.last_name}" if b.user else "Bilinmiyor",
                        user_email=b.user.email if b.user else "Bilinmiyor",
                        book_id=b.book_id,
                        book_title=b.book.title if b.book else "Bilinmiyor",
                        borrow_date=_to_date(b.borrow_date),
                        due_date=_to_date(b.due_date),
                        return_date=_to_date(b.return_date),
                        status="RETURNED",
                        return_condition=b.return_condition or "GOOD",
                        damage_penalty=float(b.damage_penalty or 0.0),
                        overdue_days=max(0, overdue_days),
                        penalty_amount=penalty,
                        is_penalty_paid=False,
                    )
                )
        else:
            if b.approval_status == "PENDING_BORROW":
                continue
            # Aktif ve süresi geçmiş (OVERDUE)
            due_d = _to_date(b.due_date)
            is_overdue = b.status == BorrowingStatus.OVERDUE or (due_d is not None and today > due_d)
            if is_overdue and not b.is_penalty_paid:
                overdue_days = b.overdue_days or (max(1, (today - due_d).days) if due_d else 1)
                penalty = round(overdue_days * settings.DAILY_PENALTY_RATE + float(b.damage_penalty or 0.0), 2)
                total_unpaid += penalty
                items.append(
                    UnpaidPenaltyItem(
                        borrowing_id=b.id,
                        user_id=b.user_id,
                        user_full_name=f"{b.user.first_name} {b.user.last_name}" if b.user else "Bilinmiyor",
                        user_email=b.user.email if b.user else "Bilinmiyor",
                        book_id=b.book_id,
                        book_title=b.book.title if b.book else "Bilinmiyor",
                        borrow_date=_to_date(b.borrow_date),
                        due_date=due_d,
                        return_date=None,
                        status="OVERDUE",
                        return_condition=b.return_condition or "GOOD",
                        damage_penalty=float(b.damage_penalty or 0.0),
                        overdue_days=overdue_days,
                        penalty_amount=penalty,
                        is_penalty_paid=False,
                    )
                )

    return UnpaidPenaltiesResponse(
        total_unpaid_amount=round(total_unpaid, 2),
        debtor_count=len(items),
        items=items,
    )

