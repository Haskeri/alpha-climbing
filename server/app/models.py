from datetime import UTC, date, datetime

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

ROLE_CLIMBER = "climber"
ROLE_LEADER = "leader"
ROLE_ADMIN = "admin"
ROLES = (ROLE_CLIMBER, ROLE_LEADER, ROLE_ADMIN)


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


group_members = Table(
    "group_members",
    Base.metadata,
    Column("group_id", ForeignKey("climbing_groups.id"), primary_key=True),
    Column("climber_id", ForeignKey("climbers.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    full_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default=ROLE_CLIMBER)
    is_approved: Mapped[bool] = mapped_column(default=False)
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

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


class Peak(Base):
    __tablename__ = "peaks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    height: Mapped[int]
    country: Mapped[str] = mapped_column(String(128))
    groups: Mapped[list["ClimbingGroup"]] = relationship(back_populates="peak")

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


class Climber(Base):
    __tablename__ = "climbers"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(128))
    birth_year: Mapped[int | None]
    rank: Mapped[str] = mapped_column(String(64), default="без разряда")
    groups: Mapped[list["ClimbingGroup"]] = relationship(
        secondary=group_members, back_populates="members"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "birth_year": self.birth_year,
            "rank": self.rank,
            "ascents": sum(1 for g in self.groups if g.end_date <= date.today()),
        }


class ClimbingGroup(Base):
    __tablename__ = "climbing_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    peak_id: Mapped[int] = mapped_column(ForeignKey("peaks.id"))
    start_date: Mapped[date]
    end_date: Mapped[date]
    leader_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    peak: Mapped[Peak] = relationship(back_populates="groups")
    leader: Mapped[User | None] = relationship()
    members: Mapped[list[Climber]] = relationship(secondary=group_members, back_populates="groups")

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
