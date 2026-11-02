"""部屋番号で登録された住人を削除する移行用スクリプト。

予約がある住人は削除せず、スキップして表示します。
先に予約をキャンセルしてから再実行してください。

使い方:
  python remove_room_number_members.py
"""

import sys

from app import models
from app.database import SessionLocal
from app.schemas import ROOM_NUMBER_PATTERN


def main() -> None:
    db = SessionLocal()

    try:
        members = db.query(models.Member).order_by(models.Member.id).all()
        targets = [
            member
            for member in members
            if ROOM_NUMBER_PATTERN.fullmatch(member.name)
        ]

        if not targets:
            print("部屋番号で登録された住人は見つかりませんでした。")
            return

        deleted = 0
        skipped = 0

        for member in targets:
            has_reservation = (
                db.query(models.Reservation.id)
                .filter(models.Reservation.member_id == member.id)
                .first()
            )
            if has_reservation:
                print(f"スキップ: ID:{member.id} {member.name}（予約あり）")
                skipped += 1
                continue

            print(f"削除: ID:{member.id} {member.name}")
            db.delete(member)
            deleted += 1

        db.commit()
        print(f"削除: {deleted}件 / スキップ: {skipped}件")

    except Exception as error:
        db.rollback()
        print(f"エラーが発生しました: {error}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
