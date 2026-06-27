#!/usr/bin/env python
"""插入示例数据"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime

from backend.database import SessionLocal, init_db
from backend.database.models import Equipment, FaultCase, KnowledgeEntry


def seed():
    init_db()
    db = SessionLocal()

    try:
        # ---------- 设备 ----------
        equip = Equipment(
            name="数控铣床 XK-850",
            model="XK-850",
            category="数控机床",
            manufacturer="大连机床厂",
            location="A车间-01号工位",
            description="三轴立式数控铣床，适用于精密零件加工",
        )
        db.add(equip)
        db.flush()

        # ---------- 故障案例 ----------
        fault = FaultCase(
            equipment_id=equip.id,
            title="主轴异响",
            symptom="运行时主轴发出周期性金属摩擦声，转速越高声音越明显",
            cause="主轴轴承磨损严重，润滑不足",
            solution="更换主轴轴承（型号 NSK 7014），添加专用润滑脂",
            severity="high",
            occurred_at=datetime(2025, 12, 15, 14, 30),
        )
        db.add(fault)

        # ---------- 知识条目 ----------
        knowledge = KnowledgeEntry(
            equipment_id=equip.id,
            title="XK-850 操作手册 - 主轴维护",
            content="## 主轴日常维护\n\n1. 每日开机前检查主轴润滑油位\n"
                     "2. 每周清洁主轴锥孔\n3. 每月检查主轴精度\n"
                     "4. 每季度更换主轴轴承润滑脂",
            source_type="manual",
            tags="主轴,维护,操作手册",
        )
        db.add(knowledge)

        db.commit()
        print("[OK] 示例数据插入成功！")
        print(f"  - 设备: {equip.name}")
        print(f"  - 故障案例: {fault.title}")
        print(f"  - 知识条目: {knowledge.title}")

    except Exception as e:
        db.rollback()
        print(f"[FAIL] 数据插入失败: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
