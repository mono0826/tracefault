import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
    
import asyncio
from langchain_core.messages import HumanMessage
from backend.models.get_models import get_stream_llm_model

async def main():
    chat = get_stream_llm_model() 
    messages = [HumanMessage(content="Tell me a short joke.")]
    try:
        async for chunk in chat.astream(messages):
            print(chunk.content, end="", flush=True)
        print("\nStream finished.")
    except Exception as e:
        print(f"\nError during basic stream: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())