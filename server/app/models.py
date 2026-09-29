from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

ROLE_CLIMBER = "climber"
ROLE_LEADER = "leader"
ROLE_ADMIN = "admin"
ROLES = (ROLE_CLIMBER, ROLE_LEADER, ROLE_ADMIN)

group_members = db.Table(
    "group_members",
    db.Column("group_id", db.Integer, db.ForeignKey("climbing_groups.id"), primary_key=True),
    db.Column("climber_id", db.Integer, db.ForeignKey("climbers.id"), primary_key=True),
)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(16), nullable=False, default=ROLE_CLIMBER)
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "login": self.login,
            "full_name": self.full_name,
            "role": self.role,
            "is_approved": self.is_approved,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }


class Peak(db.Model):
    __tablename__ = "peaks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    country = db.Column(db.String(128), nullable=False)
    groups = db.relationship("ClimbingGroup", back_populates="peak")

    @property
    def has_ascent(self):
        """Восхождение считается совершённым, если хотя бы одна группа завершила выход."""
        today = date.today()
        return any(g.end_date <= today for g in self.groups)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "height": self.height,
            "country": self.country,
            "has_ascent": self.has_ascent,
            "groups_count": len(self.groups),
        }


class Climber(db.Model):
    __tablename__ = "climbers"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(128), nullable=False)
    birth_year = db.Column(db.Integer)
    rank = db.Column(db.String(64), nullable=False, default="без разряда")
    groups = db.relationship("ClimbingGroup", secondary=group_members, back_populates="members")

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "birth_year": self.birth_year,
            "rank": self.rank,
            "ascents": sum(1 for g in self.groups if g.end_date <= date.today()),
        }


class ClimbingGroup(db.Model):
    __tablename__ = "climbing_groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    peak_id = db.Column(db.Integer, db.ForeignKey("peaks.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    peak = db.relationship("Peak", back_populates="groups")
    leader = db.relationship("User")
    members = db.relationship("Climber", secondary=group_members, back_populates="groups")

    def to_dict(self):
        today = date.today()
        if self.end_date < today:
            status = "completed"
        elif self.start_date <= today:
            status = "active"
        else:
            status = "planned"
        return {
            "id": self.id,
            "name": self.name,
            "peak": {"id": self.peak.id, "name": self.peak.name, "height": self.peak.height},
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "status": status,
            "leader": self.leader.full_name if self.leader else None,
            "members": [{"id": m.id, "full_name": m.full_name, "rank": m.rank} for m in self.members],
        }
