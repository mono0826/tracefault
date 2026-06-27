import time
import os
import pickle
import concurrent.futures
from typing import List, Tuple, Optional
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)

from backend.graph.core import retry, generate_hash
from backend.config.settings import MAX_WORKERS as DEFAULT_MAX_WORKERS, BATCH_SIZE as DEFAULT_BATCH_SIZE
from backend.pipelines.models import Chunk


class EntityRelationExtractor:
    """
    实体关系提取器，负责从文本中提取实体和关系。
    使用LLM分析文本块，生成结构化的实体和关系数据。
    """
    
    def __init__(self, llm, system_template, human_template, 
             entity_types: List[str], relationship_types: List[str],
             cache_dir="./cache/graph", max_workers=4, batch_size=5):
        """
        初始化实体关系提取器
        
        Args:
            llm: 语言模型
            system_template: 系统提示模板
            human_template: 用户提示模板
            entity_types: 实体类型列表
            relationship_types: 关系类型列表
            cache_dir: 缓存目录
            max_workers: 并行工作线程数
            batch_size: 批处理大小
        """
        self.llm = llm
        self.entity_types = entity_types
        self.relationship_types = relationship_types
        self.chat_history = []
        
        # 设置分隔符
        self.tuple_delimiter = " : "
        self.record_delimiter = "\n"
        self.completion_delimiter = "\n\n"
        
        # 创建提示模板
        system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)
        human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
        
        self.chat_prompt = ChatPromptTemplate.from_messages([
            system_message_prompt,
            MessagesPlaceholder("chat_history"),
            human_message_prompt
        ])
        
        # 创建处理链
        self.chain = self.chat_prompt | self.llm
        
        # 缓存设置
        self.cache_dir = cache_dir
        self.enable_cache = True
        
        # 确保缓存目录存在
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        # 并行处理配置
        self.max_workers = max_workers or DEFAULT_MAX_WORKERS
        self.batch_size = batch_size or DEFAULT_BATCH_SIZE
        
        # 缓存统计
        self.cache_hits = 0
        self.cache_misses = 0
    
    def _cache_path(self, cache_key: str) -> str:
        """
        获取缓存文件路径
        
        Args:
            cache_key: 缓存键
            
        Returns:
            str: 缓存文件路径
        """
        return os.path.join(self.cache_dir, f"{cache_key}.pkl")
    
    def _save_to_cache(self, cache_key: str, result: str) -> None:
        """
        保存结果到缓存
        
        Args:
            cache_key: 缓存键
            result: 结果
        """
        if not self.enable_cache:
            return
            
        cache_path = self._cache_path(cache_key)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(result, f)
        except Exception as e:
            print(f"缓存保存错误: {e}")
    
    def _load_from_cache(self, cache_key: str) -> Optional[str]:
        """
        从缓存加载结果
        
        Args:
            cache_key: 缓存键
            
        Returns:
            Optional[str]: 缓存的结果，如果不存在则返回None
        """
        if not self.enable_cache:
            return None
            
        cache_path = self._cache_path(cache_key)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    result = pickle.load(f)
                    self.cache_hits += 1
                    return result
            except Exception as e:
                print(f"缓存加载错误: {e}")
        
        self.cache_misses += 1
        return None
        
    def process_chunks(self, file_contents: List[Tuple[str, List[Chunk]]]) -> List[Tuple[str, List[Chunk], List[str]]]:
        """
        并行处理所有文件的 Chunk，用 LLM 提取实体和关系

        Args:
            file_contents: [(file_name, [Chunk, ...]), ...]

        Returns:
            [(file_name, [Chunk, ...], [LLM结果, ...]), ...]
        """
        t0 = time.time()
        all_results = []
        total_chunks = sum(len(fc[1]) for fc in file_contents)
        processed = 0

        for file_name, chunks in file_contents:
            # 预分配结果列表，保持原始顺序
            ordered = [None] * len(chunks)
            todo = []

            # 查缓存（chunk.chunk_id 本身就是 SHA1(content)）
            for i, chunk in enumerate(chunks):
                cached = self._load_from_cache(chunk.chunk_id)
                if cached is not None:
                    ordered[i] = cached
                else:
                    todo.append(i)

            # 未缓存的并行调 LLM
            if todo:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_idx = {
                        executor.submit(self._process_single_chunk, chunks[i].content): i
                        for i in todo
                    }
                    for future in concurrent.futures.as_completed(future_to_idx):
                        i = future_to_idx[future]
                        try:
                            result = future.result()
                            ordered[i] = result
                            self._save_to_cache(chunks[i].chunk_id, result)
                            processed += 1
                        except Exception as exc:
                            print(f'Chunk {chunks[i].chunk_id} 处理异常: {exc}')
                            retry_count = 0
                            while retry_count < 3:
                                try:
                                    print(f'尝试重试, 第 {retry_count+1} 次')
                                    result = self._process_single_chunk(chunks[i].content)
                                    ordered[i] = result
                                    self._save_to_cache(chunks[i].chunk_id, result)
                                    break
                                except Exception as e:
                                    print(f'重试失败: {e}')
                                    retry_count += 1
                                    time.sleep(1)
                            if ordered[i] is None:
                                ordered[i] = ""

            cache_ratio = self.cache_hits / (self.cache_hits + self.cache_misses) * 100 \
                if (self.cache_hits + self.cache_misses) > 0 else 0
            print(f"  {file_name}: {len(chunks)} 个 chunk, 缓存命中率: {cache_ratio:.1f}%")

            all_results.append((file_name, chunks, ordered))

        process_time = time.time() - t0
        print(f"所有 chunks 处理完成, 总耗时: {process_time:.2f}秒, "
              f"平均每 chunk: {process_time/total_chunks:.2f}秒")
        return all_results
    
    def process_chunks_batch(self, file_contents: List[Tuple[str, List[Chunk]]],
                             progress_callback=None) -> List[Tuple[str, List[Chunk], List[str]]]:
        """
        批量处理chunks，将多个 chunk 合并到一个 LLM 请求，减少调用次数

        Args:
            file_contents: [(file_name, [Chunk, ...]), ...]
            progress_callback: 进度回调，每处理一个 chunk 调用一次 callback(index)

        Returns:
            [(file_name, [Chunk, ...], [LLM结果, ...]), ...]
        """
        all_results = []

        for file_name, chunks in file_contents:
            results = []

            # 根据平均 chunk 大小动态调整批处理大小
            chunk_lengths = [len(chunk.content) for chunk in chunks]
            avg_chunk_size = sum(chunk_lengths) / len(chunk_lengths) if chunk_lengths else 0
            dynamic_batch_size = max(1, min(self.batch_size, int(10000 / (avg_chunk_size + 1))))

            for i in range(0, len(chunks), dynamic_batch_size):
                batch_chunks = chunks[i:i+dynamic_batch_size]

                # 缓存检查
                cached_batch_results = [self._load_from_cache(c.chunk_id) for c in batch_chunks]

                # 如果全部已缓存，跳过 LLM
                if None not in cached_batch_results:
                    results.extend(cached_batch_results)
                    if progress_callback:
                        for j in range(len(batch_chunks)):
                            progress_callback(i + j)
                    continue

                # 合并多个 chunk 文本，用分隔符隔开
                batch_text = f"\n{'-'*50}\n".join(c.content for c in batch_chunks)

                try:
                    batch_response = self.chain.invoke({
                        "chat_history": self.chat_history,
                        "entity_types": self.entity_types,
                        "relationship_types": self.relationship_types,
                        "tuple_delimiter": self.tuple_delimiter,
                        "record_delimiter": self.record_delimiter,
                        "completion_delimiter": self.completion_delimiter,
                        "input_text": batch_text,
                    })

                    batch_results = self._parse_batch_response(batch_response.content)

                    # 数量不匹配 → 逐个退火
                    if len(batch_results) != len(batch_chunks):
                        batch_results = []
                        for idx, chunk in enumerate(batch_chunks):
                            cached = cached_batch_results[idx]
                            if cached is not None:
                                batch_results.append(cached)
                            else:
                                batch_results.append(self._process_single_chunk(chunk.content))
                    else:
                        for idx, result in enumerate(batch_results):
                            if cached_batch_results[idx] is None:
                                self._save_to_cache(batch_chunks[idx].chunk_id, result)

                    results.extend(batch_results)
                except Exception as e:
                    print(f"批处理错误，切换到单个处理: {e}")
                    for chunk in batch_chunks:
                        try:
                            results.append(self._process_single_chunk(chunk.content))
                        except Exception as e2:
                            print(f"单个 chunk 处理失败: {e2}")
                            results.append("")

                if progress_callback:
                    for j in range(len(batch_chunks)):
                        progress_callback(i + j)

            all_results.append((file_name, chunks, results))

        return all_results

    def _parse_batch_response(self, batch_content: str) -> List[str]:
        """
        解析批量响应，将其分割为单独的结果
        
        Args:
            batch_content: 批处理响应内容
            
        Returns:
            List[str]: 分割后的结果列表
        """
        # 使用分隔符分割响应
        parts = batch_content.split(f"\n{'-'*50}\n")
        return [part.strip() for part in parts]
    
    @retry(times=3, exceptions=(Exception,), delay=1.0)
    def _process_single_chunk(self, input_text: str) -> str:
        """
        处理单个文本块（调用 LLM 并缓存结果）

        Args:
            input_text: 输入文本

        Returns:
            str: 处理结果
        """
        cache_key = self._generate_cache_key(input_text)

        response = self.chain.invoke({
            "chat_history": self.chat_history,
            "entity_types": self.entity_types,
            "relationship_types": self.relationship_types,
            "tuple_delimiter": self.tuple_delimiter,
            "record_delimiter": self.record_delimiter,
            "completion_delimiter": self.completion_delimiter,
            "input_text": input_text
        })

        result = response.content
        self._save_to_cache(cache_key, result)
        return result
    