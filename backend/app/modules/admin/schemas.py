import uuid
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class DashboardStats(BaseModel):
    total_users: int
    total_books: int
    active_borrowings: int
    pending_reservations: int


class DashboardResponse(BaseModel):
    message: str
    stats: DashboardStats


class UnpaidPenaltyItem(BaseModel):
    borrowing_id: uuid.UUID = Field(..., description="Ödünç kaydı benzersiz kimliği")
    user_id: uuid.UUID = Field(..., description="Borçlu kullanıcı kimliği")
    user_full_name: str = Field(..., description="Kullanıcı adı soyadı")
    user_email: str = Field(..., description="Kullanıcı e-posta adresi")
    book_id: uuid.UUID = Field(..., description="Kitap kimliği")
    book_title: str = Field(..., description="Kitap başlığı")
    borrow_date: date = Field(..., description="Ödünç alınma tarihi")
    due_date: date = Field(..., description="Son teslim tarihi")
    return_date: date | datetime | None = Field(None, description="İade tarihi (iade edilmişse)")
    status: str = Field(..., description="Durum: OVERDUE (Gecikmiş Aktif) veya RETURNED (İade Edilmiş/Ödenmemiş)")
    return_condition: str = Field("GOOD", description="Fiziksel durum: GOOD, DAMAGED, LOST")
    damage_penalty: float = Field(0.0, description="Hasar veya kayıp tazminatı (TL)")
    overdue_days: int = Field(..., description="Geciken gün sayısı")
    penalty_amount: float = Field(..., description="Hesaplanan / tahakkuk eden ceza tutarı (TL)")
    is_penalty_paid: bool = Field(False, description="Ceza ödendi mi?")

    model_config = ConfigDict(from_attributes=True)


class UnpaidPenaltiesResponse(BaseModel):
    total_unpaid_amount: float = Field(..., description="Toplam tahsil edilmemiş ceza borcu tutarı (TL)")
    debtor_count: int = Field(..., description="Borçlu kayıt sayısı")
    items: list[UnpaidPenaltyItem] = Field(default_factory=list, description="Ödenmemiş ceza kayıtları")


class SystemLogEntry(BaseModel):
    id: str = Field(..., description="Log kayıt kimliği")
    timestamp: str = Field(..., description="İşlem tarihi ve saati (ISO formatı)")
    category: str = Field(..., description="Kategori: AUTH, BORROWING, RESERVATION, PENALTY, REVIEW, CATALOG, SYSTEM")
    level: str = Field(..., description="Log seviyesi: INFO, WARNING, ERROR")
    message: str = Field(..., description="İşlem açıklaması")
