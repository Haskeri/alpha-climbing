"""Начальное наполнение БД демонстрационными данными (выполняется, если БД пуста)."""
from datetime import date

from .models import ROLE_ADMIN, ROLE_CLIMBER, ROLE_LEADER, Climber, ClimbingGroup, Peak, User, db

USERS = [
    ("anufriev", "Anufriev2026!", "Ануфриев Платон Дмитриевич", ROLE_LEADER),
    ("shemchuk", "Shemchuk2026!", "Шемчук Мирон Денисович", ROLE_ADMIN),
    ("smirnova", "Climber2026!", "Смирнова Ольга Игоревна", ROLE_CLIMBER),
]

PEAKS = [
    ("Эверест", 8849, "Непал / Китай"),
    ("Пик Исмоила Сомони", 7495, "Таджикистан"),
    ("Пик Ленина", 7134, "Киргизия / Таджикистан"),
    ("Аконкагуа", 6961, "Аргентина"),
    ("Килиманджаро", 5895, "Танзания"),
    ("Эльбрус", 5642, "Россия"),
    ("Казбек", 5033, "Грузия"),
    ("Монблан", 4808, "Франция / Италия"),
    ("Белуха", 4506, "Россия"),
]

CLIMBERS = [
    ("Ануфриев Платон Дмитриевич", 2006, "КМС"),
    ("Шемчук Мирон Денисович", 2006, "1 разряд"),
    ("Иванов Сергей Петрович", 1988, "КМС"),
    ("Кузнецова Анна Викторовна", 1995, "1 разряд"),
    ("Орлов Дмитрий Алексеевич", 1991, "МС"),
    ("Соколов Илья Романович", 2001, "2 разряд"),
    ("Морозова Екатерина Олеговна", 1999, "3 разряд"),
    ("Волков Никита Андреевич", 2003, "без разряда"),
]

GROUPS = [
    ("Эльбрус-2026", "Эльбрус", date(2026, 7, 12), date(2026, 7, 20), [0, 1, 3, 5], "anufriev"),
    ("Казбек: южный маршрут", "Казбек", date(2026, 8, 3), date(2026, 8, 10), [0, 2, 4], "anufriev"),
    ("Белуха — осенний выход", "Белуха", date(2026, 9, 28), date(2026, 10, 14), [1, 3, 6, 7], "shemchuk"),
    ("Пик Ленина-2027", "Пик Ленина", date(2027, 7, 5), date(2027, 7, 28), [0, 1, 4], "anufriev"),
]


def seed_if_empty(app):
    if User.query.first() is not None:
        return
    users = {}
    for login, password, full_name, role in USERS:
        user = User(login=login, full_name=full_name, role=role, is_approved=True)
        user.set_password(password)
        db.session.add(user)
        users[login] = user
    peaks = {name: Peak(name=name, height=h, country=c) for name, h, c in PEAKS}
    db.session.add_all(peaks.values())
    climbers = [Climber(full_name=n, birth_year=y, rank=r) for n, y, r in CLIMBERS]
    db.session.add_all(climbers)
    for name, peak, start, end, members, leader in GROUPS:
        db.session.add(
            ClimbingGroup(
                name=name,
                peak=peaks[peak],
                start_date=start,
                end_date=end,
                leader=users[leader],
                members=[climbers[i] for i in members],
            )
        )
    db.session.commit()
    app.logger.info("БД заполнена демонстрационными данными")
