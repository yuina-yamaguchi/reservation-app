from sqlalchemy.orm import Session

from . import models

DEFAULT_CARS = [
    {"name": "プリウス", "plate": "品川 300 あ 1234", "color": "白"},
    {"name": "ヴォクシー", "plate": "品川 500 い 5678", "color": "黒"},
    {"name": "フィット", "plate": "品川 100 う 9012", "color": "シルバー"},
]

DEFAULT_MEMBERS = ["101", "102", "201", "202"]


def seed_defaults(db: Session) -> dict[str, int]:
    """空のテーブルにだけ初期データを投入する。"""
    cars_created = 0
    members_created = 0

    if db.query(models.Car).count() == 0:
        db.add_all([models.Car(**car) for car in DEFAULT_CARS])
        cars_created = len(DEFAULT_CARS)

    if db.query(models.Member).count() == 0:
        db.add_all([models.Member(name=name) for name in DEFAULT_MEMBERS])
        members_created = len(DEFAULT_MEMBERS)

    db.commit()
    return {"cars_created": cars_created, "members_created": members_created}
