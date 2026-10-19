"""Yönetim komutları.

Kullanım (proje kökünden):
    docker compose exec backend python -m app.cli make-admin <email>
    docker compose exec backend python -m app.cli revoke-admin <email>
"""

import argparse
import sys

import app.models  # noqa: F401  - tüm mapper'ları kaydeder
from app.core.database import SessionLocal
from app.modules.auth.models import RoleName
from app.modules.auth.service import get_or_create_role, get_user_by_email


def _set_admin(email: str, grant: bool) -> int:
    with SessionLocal() as db:
        user = get_user_by_email(db, email)
        if user is None:
            print(f"HATA: '{email}' adresiyle kayıtlı kullanıcı bulunamadı.", file=sys.stderr)
            return 1

        admin_role = get_or_create_role(db, RoleName.ADMIN)
        has_admin = admin_role in user.roles

        if grant and not has_admin:
            user.roles.append(admin_role)
        elif not grant and has_admin:
            user.roles.remove(admin_role)
        db.commit()

        roles = ", ".join(sorted(r.name.value for r in user.roles))
        print(f"OK: {user.email} -> roller: [{roles}]")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("make-admin", "Kullanıcıya ADMIN rolü ver"),
        ("revoke-admin", "Kullanıcıdan ADMIN rolünü al"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("email")

    args = parser.parse_args()
    return _set_admin(args.email, grant=args.command == "make-admin")


if __name__ == "__main__":
    raise SystemExit(main())

