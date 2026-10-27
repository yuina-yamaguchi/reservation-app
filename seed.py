"""初期データ投入スクリプト。

車3台・住人4人のサンプルデータを登録します。
既にデータがあるテーブルはスキップするため、再実行しても安全です。

使い方:
  python seed.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import models
from app.database import Base, SessionLocal, engine
from app.seed_data import seed_defaults


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        result = seed_defaults(db)

        if result["cars_created"]:
            print(f"車を{result['cars_created']}台登録しました。")
        else:
            print("車のデータが既に存在するためスキップしました。")

        if result["members_created"]:
            print(f"住人を{result['members_created']}人登録しました。")
        else:
            print("住人のデータが既に存在するためスキップしました。")

        print()
        print("【車】")
        for car in db.query(models.Car).all():
            print(f"  ID:{car.id}  {car.name}  {car.color}  {car.plate}")
        print()
        print("【住人】")
        for member in db.query(models.Member).all():
            print(f"  ID:{member.id}  {member.name}")

    except Exception as error:
        db.rollback()
        print(f"エラーが発生しました: {error}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
