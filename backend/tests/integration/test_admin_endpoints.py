from datetime import date, timedelta


def test_admin_unpaid_penalties_unauthorized_and_forbidden(client, auth_headers):
    # Token olmadan -> 401
    res1 = client.get("/api/v1/admin/unpaid-penalties")
    assert res1.status_code == 401

    # Normal kullanıcı (USER rolü) -> 403
    res2 = client.get("/api/v1/admin/unpaid-penalties", headers=auth_headers)
    assert res2.status_code == 403


def test_admin_unpaid_penalties_and_collection_flow(client, auth_headers, admin_headers, test_book):
    # 1. Normal kullanıcı kitap ödünç alır
    due_date = (date.today() + timedelta(days=14)).isoformat()
    borrow_res = client.post(
        "/api/v1/borrowings",
        json={"book_id": str(test_book.id), "due_date": due_date},
        headers=auth_headers,
    )
    assert borrow_res.status_code == 201
    borrow_id = borrow_res.json()["id"]

    # 2. Henüz gecikme yokken borçlu listesi boştur
    unpaid_res_initial = client.get("/api/v1/admin/unpaid-penalties", headers=admin_headers)
    assert unpaid_res_initial.status_code == 200
    assert unpaid_res_initial.json()["debtor_count"] == 0

    # 3. Gecikme simülasyonu uygula (due_date -5 gün geri çekilir)
    sim_res = client.patch(f"/api/v1/admin/borrowings/{borrow_id}/simulate-overdue", headers=admin_headers)
    assert sim_res.status_code == 200

    # 4. Artık borçlu listesinde görünmelidir
    unpaid_res_overdue = client.get("/api/v1/admin/unpaid-penalties", headers=admin_headers)
    assert unpaid_res_overdue.status_code == 200
    data = unpaid_res_overdue.json()
    assert data["debtor_count"] == 1
    assert data["total_unpaid_amount"] > 0
    item = data["items"][0]
    assert item["borrowing_id"] == borrow_id
    assert item["status"] == "OVERDUE"
    assert item["penalty_amount"] > 0
    assert item["is_penalty_paid"] is False

    # 5. Admin elden tahsilat yapar ("Tahsil Et / Borcu Kapat")
    pay_res = client.post(f"/api/v1/borrowings/{borrow_id}/pay-penalty", headers=admin_headers)
    assert pay_res.status_code == 200
    assert pay_res.json()["is_penalty_paid"] is True

    # 6. Borç ödendikten sonra listeden düşer
    unpaid_res_after = client.get("/api/v1/admin/unpaid-penalties", headers=admin_headers)
    assert unpaid_res_after.status_code == 200
    assert unpaid_res_after.json()["debtor_count"] == 0


def test_admin_system_logs_endpoint(client, auth_headers, admin_headers):
    # 1. Yetkisiz erişim kontrolü
    assert client.get("/api/v1/admin/logs").status_code == 401
    assert client.get("/api/v1/admin/logs", headers=auth_headers).status_code == 403

    # 2. Admin logları listeler
    res = client.get("/api/v1/admin/logs", headers=admin_headers)
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)
    assert len(logs) >= 1

    first_log = logs[0]
    assert "id" in first_log
    assert "timestamp" in first_log
    assert "category" in first_log
    assert "level" in first_log
    assert "message" in first_log

    # 3. Kategoriye ve seviyeye göre filtreleme
    filtered_res = client.get("/api/v1/admin/logs?level=INFO", headers=admin_headers)
    assert filtered_res.status_code == 200
    for l in filtered_res.json():
        assert l["level"] == "INFO"

