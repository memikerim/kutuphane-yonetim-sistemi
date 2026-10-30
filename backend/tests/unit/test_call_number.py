import uuid
from datetime import date, timedelta
from app.modules.catalog.call_number import (
    generate_dewey_call_number,
    format_copy_code,
    format_barcode,
    get_cutter_number,
)
from app.modules.catalog.models import Book
from app.modules.borrowing.models import Borrowing, BorrowingStatus
from app.modules.borrowing.schemas import BorrowingCreate, AdminApproveBorrowRequest, AdminApproveReturnRequest
from app.modules.borrowing import service as borrowing_service


def test_dewey_and_cutter_generation():
    # George Orwell - 1984 (Distopya / Roman)
    cn = generate_dewey_call_number(
        categories=["Distopya", "Roman"],
        author_name="George Orwell",
        title="1984",
        published_year=1949,
    )
    assert "823.91" in cn
    assert "ORW" in cn
    assert "1949" in cn

    # Nâzım Hikmet - Şiir
    cn2 = generate_dewey_call_number(
        categories=["Şiir", "Türk Edebiyatı"],
        author_name="Nâzım Hikmet",
        title="Memleketimden İnsan Manzaraları",
        published_year=1966,
    )
    assert "894.31" in cn2
    assert "HIK" in cn2


def test_copy_code_formatting():
    code1 = format_copy_code("978-975-07-1853-3", 1)
    code2 = format_copy_code("978-975-07-1853-3", 2)
    barcode1 = format_barcode("978-975-07-1853-3", 1)

    assert code1 == "DEM-9789750718533-K1"
    assert code2 == "DEM-9789750718533-K2"
    assert barcode1 == "978975071853301"


def test_borrowing_copy_code_assignment_and_lifecycle(db_session, test_user, test_book, admin_user):
    # test_book başlangıçta stock_count=5 varsayalım
    test_book.stock_count = 3
    db_session.commit()

    # 1. Kullanıcı ödünç talebi açar (request_approval=True)
    borrow_req = BorrowingCreate(
        book_id=test_book.id,
        due_date=date.today() + timedelta(days=14),
        request_approval=True,
    )
    b1 = borrowing_service.create_borrowing(db_session, test_user, borrow_req)
    # İlk nüsha (K1) atanmalıdır
    assert b1.copy_code is not None
    assert "-K1" in b1.copy_code

    # Kitabın kopyaları listesinde K1 'Teslim Onayı Bekliyor' olmalıdır
    copies = test_book.copies
    assert len(copies) >= 3
    copy1 = next(c for c in copies if c["copy_number"] == 1)
    assert copy1["status"] == "PENDING_BORROW"
    assert copy1["status_label"] == "Teslim Onayı Bekliyor"

    # 2. Görevli onaylar
    approved = borrowing_service.admin_approve_borrow(db_session, admin_user, b1.id)
    assert approved.approval_status == "APPROVED"
    assert "-K1" in approved.copy_code

    copies_after_approve = test_book.copies
    copy1_approved = next(c for c in copies_after_approve if c["copy_number"] == 1)
    assert copy1_approved["status"] == "BORROWED"
    assert copy1_approved["status_label"] == "Ödünç Verildi"

    # 3. İade tamamlanır
    ret_req = AdminApproveReturnRequest(return_condition="GOOD")
    returned = borrowing_service.admin_approve_return(db_session, admin_user, b1.id, ret_req)
    assert returned.status == BorrowingStatus.RETURNED

    # İadeden sonra K1 tekrar Rafta / Müsait olmalıdır
    copies_after_return = test_book.copies
    copy1_returned = next(c for c in copies_after_return if c["copy_number"] == 1)
    assert copy1_returned["status"] == "AVAILABLE"
    assert copy1_returned["status_label"] == "Rafta (Müsait)"
