#!/usr/bin/env python
"""初始化数据库：创建所有表"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db


def main():
    print("正在连接数据库...")
    try:
        init_db()
        print("[OK] 数据库初始化完成，所有表已创建。")
    except Exception as e:
        print(f"[FAIL] 数据库初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
