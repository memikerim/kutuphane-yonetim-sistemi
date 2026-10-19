from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_users: int
    total_books: int
    active_borrowings: int
    pending_reservations: int


class DashboardResponse(BaseModel):
    message: str
    stats: DashboardStats

