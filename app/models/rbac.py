from datetime import datetime
from app.extensions import db

# Every permission string the admin panel currently gates. Keep this list
# in sync with @permission_required() calls across the admin routes.
ALL_PERMISSIONS = [
    "kyc.review",
    "support.manage",
    "users.manage",
    "referrals.manage",
    "content.manage",
    "templates.manage",
    "gateways.manage",
    "roles.manage",
    "wallet.adjust",
]


class Role(db.Model):
    """Named permission bundle. `User.role` (a plain string, unchanged for
    backward compatibility) is matched against Role.name at check time —
    no FK/migration needed on the users table.
    """

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)  # matches User.role values
    description = db.Column(db.String(150))
    permissions = db.Column(db.JSON, default=list)  # list[str] subset of ALL_PERMISSIONS
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def has(self, permission: str) -> bool:
        return permission in (self.permissions or [])

    def __repr__(self):
        return f"<Role {self.name}>"


def seed_default_roles():
    """Idempotent — call at startup. Creates sensible defaults matching the
    roles already hardcoded in User.role (player/admin/ceo/support)."""
    defaults = {
        "ceo": ALL_PERMISSIONS,  # full access
        "admin": [p for p in ALL_PERMISSIONS if p != "roles.manage"],
        "support": ["kyc.review", "support.manage"],
        "player": [],
    }
    for name, perms in defaults.items():
        role = Role.query.filter_by(name=name).first()
        if not role:
            db.session.add(Role(name=name, permissions=perms, description=f"Default {name} role"))
    db.session.commit()
