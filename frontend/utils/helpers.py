"""前端工具函数"""

import uuid


def generate_session_id() -> str:
    """生成对话会话 ID"""
    return uuid.uuid4().hex[:16]
