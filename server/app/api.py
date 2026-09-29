import socket
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import __version__
from .models import (
    ROLE_ADMIN,
    ROLE_CLIMBER,
    ROLE_LEADER,
    ROLES,
    Climber,
    ClimbingGroup,
    Peak,
    User,
    db,
)

api = Blueprint("api", __name__)

TOKEN_TTL = 12 * 60 * 60
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 5


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="alpha-auth")


def error(message, status):
    return jsonify({"error": message}), status


def _current_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        user_id = _serializer().loads(header[7:], max_age=TOKEN_TTL)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, user_id)
    return user if user and user.is_approved else None


def login_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = _current_user()
            if user is None:
                return error("Требуется авторизация", 401)
            if roles and user.role not in roles:
                return error("Недостаточно прав", 403)
            g.user = user
            return view(*args, **kwargs)

        return wrapper

    return decorator


def _json():
    return request.get_json(silent=True) or {}


def _parse_date(value, field):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"Поле «{field}» должно быть датой в формате ГГГГ-ММ-ДД")


@api.route("/<path:_any>", methods=["OPTIONS"])
def preflight(_any):
    return "", 204


@api.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "alpha-api",
            "version": __version__,
            "host": socket.gethostname(),
            "database": db.engine.url.get_backend_name(),
        }
    )


@api.get("/stats")
def stats():
    return jsonify(
        {
            "peaks": Peak.query.count(),
            "climbers": Climber.query.count(),
            "groups": ClimbingGroup.query.count(),
            "users": User.query.count(),
        }
    )


# ---------- Авторизация и регистрация ----------


@api.post("/auth/register")
def register():
    data = _json()
    login = (data.get("login") or "").strip()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()
    if len(login) < 3 or len(password) < 6 or not full_name:
        return error("Укажите логин (от 3 символов), пароль (от 6 символов) и ФИО", 400)
    if User.query.filter_by(login=login).first():
        return error("Пользователь с таким логином уже существует", 409)
    user = User(login=login, full_name=full_name, role=ROLE_CLIMBER, is_approved=False)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    current_app.logger.info("Новая заявка на регистрацию: %s", login)
    return jsonify({"message": "Заявка отправлена администратору", "user": user.to_dict()}), 201


@api.post("/auth/login")
def login():
    data = _json()
    user = User.query.filter_by(login=(data.get("login") or "").strip()).first()
    now = datetime.utcnow()
    if user and user.locked_until and user.locked_until > now:
        return error("Слишком много неудачных попыток. Повторите позже", 429)
    if user is None or not user.check_password(data.get("password") or ""):
        if user:
            user.failed_attempts += 1
            if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                user.failed_attempts = 0
            db.session.commit()
        current_app.logger.warning("Неудачная попытка входа: %s", data.get("login"))
        return error("Неверный логин или пароль", 401)
    if not user.is_approved:
        return error("Заявка на регистрацию ещё не подтверждена администратором", 403)
    user.failed_attempts = 0
    user.locked_until = None
    db.session.commit()
    current_app.logger.info("Пользователь %s вошёл в систему", user.login)
    return jsonify({"token": _serializer().dumps(user.id), "user": user.to_dict()})


@api.get("/auth/me")
@login_required()
def me():
    return jsonify(g.user.to_dict())


# ---------- Вершины ----------


@api.get("/peaks")
def peaks_list():
    peaks = Peak.query.order_by(Peak.height.desc()).all()
    return jsonify([p.to_dict() for p in peaks])


def _peak_fields(data):
    name = (data.get("name") or "").strip()
    country = (data.get("country") or "").strip()
    try:
        height = int(data.get("height"))
    except (TypeError, ValueError):
        raise ValueError("Высота должна быть целым числом")
    if not name or not country:
        raise ValueError("Укажите название и страну")
    if not 100 <= height <= 8849:
        raise ValueError("Высота должна быть в диапазоне 100–8849 м")
    return name, height, country


@api.post("/peaks")
@login_required(ROLE_LEADER, ROLE_ADMIN)
def peaks_create():
    try:
        name, height, country = _peak_fields(_json())
    except ValueError as exc:
        return error(str(exc), 400)
    if Peak.query.filter_by(name=name).first():
        return error("Такая вершина уже есть в каталоге", 409)
    peak = Peak(name=name, height=height, country=country)
    db.session.add(peak)
    db.session.commit()
    current_app.logger.info("%s добавил вершину «%s» (%s м)", g.user.login, name, height)
    return jsonify(peak.to_dict()), 201


@api.put("/peaks/<int:peak_id>")
@login_required(ROLE_LEADER, ROLE_ADMIN)
def peaks_update(peak_id):
    peak = db.session.get(Peak, peak_id)
    if peak is None:
        return error("Вершина не найдена", 404)
    if peak.has_ascent:
        return error("Нельзя изменить вершину, на которую уже совершено восхождение", 409)
    try:
        peak.name, peak.height, peak.country = _peak_fields(_json())
    except ValueError as exc:
        return error(str(exc), 400)
    db.session.commit()
    current_app.logger.info("%s изменил вершину #%s", g.user.login, peak_id)
    return jsonify(peak.to_dict())


# ---------- Альпинисты ----------


@api.get("/climbers")
def climbers_list():
    return jsonify([c.to_dict() for c in Climber.query.order_by(Climber.full_name).all()])


@api.post("/climbers")
@login_required(ROLE_LEADER, ROLE_ADMIN)
def climbers_create():
    data = _json()
    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        return error("Укажите ФИО альпиниста", 400)
    birth_year = data.get("birth_year") or None
    climber = Climber(
        full_name=full_name,
        birth_year=int(birth_year) if birth_year else None,
        rank=(data.get("rank") or "без разряда").strip(),
    )
    db.session.add(climber)
    db.session.commit()
    current_app.logger.info("%s добавил альпиниста «%s»", g.user.login, full_name)
    return jsonify(climber.to_dict()), 201


# ---------- Альпинистские группы ----------


@api.get("/groups")
def groups_list():
    groups = ClimbingGroup.query.order_by(ClimbingGroup.start_date.desc()).all()
    return jsonify([grp.to_dict() for grp in groups])


@api.post("/groups")
@login_required(ROLE_LEADER, ROLE_ADMIN)
def groups_create():
    data = _json()
    name = (data.get("name") or "").strip()
    peak = db.session.get(Peak, data.get("peak_id") or 0)
    if not name or peak is None:
        return error("Укажите название группы и вершину", 400)
    try:
        start = _parse_date(data.get("start_date"), "Дата начала")
        end = _parse_date(data.get("end_date"), "Дата окончания")
    except ValueError as exc:
        return error(str(exc), 400)
    if end < start:
        return error("Дата окончания не может быть раньше даты начала", 400)
    group = ClimbingGroup(name=name, peak=peak, start_date=start, end_date=end, leader=g.user)
    db.session.add(group)
    db.session.commit()
    current_app.logger.info("%s создал группу «%s» на %s", g.user.login, name, peak.name)
    return jsonify(group.to_dict()), 201


@api.post("/groups/<int:group_id>/members")
@login_required(ROLE_LEADER, ROLE_ADMIN)
def groups_add_member(group_id):
    group = db.session.get(ClimbingGroup, group_id)
    climber = db.session.get(Climber, _json().get("climber_id") or 0)
    if group is None or climber is None:
        return error("Группа или альпинист не найдены", 404)
    if climber in group.members:
        return error("Альпинист уже состоит в группе", 409)
    group.members.append(climber)
    db.session.commit()
    current_app.logger.info("%s добавил %s в группу «%s»", g.user.login, climber.full_name, group.name)
    return jsonify(group.to_dict()), 201


# ---------- Администрирование ----------


@api.get("/admin/requests")
@login_required(ROLE_ADMIN)
def admin_requests():
    pending = User.query.filter_by(is_approved=False).order_by(User.created_at).all()
    return jsonify([u.to_dict() for u in pending])


@api.post("/admin/requests/<int:user_id>/approve")
@login_required(ROLE_ADMIN)
def admin_approve(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return error("Заявка не найдена", 404)
    role = _json().get("role") or ROLE_CLIMBER
    if role not in ROLES:
        return error("Неизвестная роль", 400)
    user.is_approved = True
    user.role = role
    db.session.commit()
    current_app.logger.info("%s подтвердил заявку %s (роль %s)", g.user.login, user.login, role)
    return jsonify(user.to_dict())
