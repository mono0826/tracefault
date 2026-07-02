"""
实体预去重器：在写入 Neo4j 前，对 LLM 提取结果中的重复实体和关系做聚类合并。

Input / Output 格式（与 EntityRelationExtractor 对接）：
    [(file_name, [Chunk, ...], [LLM结果字符串, ...]), ...]

去重流程：
    1. 解析所有 LLM 结果字符串 → 全局实体集合 (name, type, desc, confidence)
    2. 按 confidence 阈值过滤低置信度实体
    3. 按 type 分组，组内做 name 模糊聚类
    4. 生成 old_name → canonical_name 映射
    5. 将映射应用到每个 LLM 字符串（实体名 + 关系引用），移除被合并的声明
"""

import re
from typing import List, Tuple, Dict, Set, Optional
from difflib import SequenceMatcher
from collections import defaultdict


class EntityDeduplicator:
    """
    实体预去重器：对 LLM 提取结果中的实体做聚类合并，
    在写入 Neo4j 前消除重复实体和关系。

    与 GraphWriter 解耦，独立完成"解析 → 过滤 → 聚类 → 映射 → 重写"全流程。
    """

    # LLM 输出格式：
    #   (entity : name : type : desc : confidence)
    #   (relationship : src : tgt : rel_type : desc : confidence)
    NODE_PATTERN = re.compile(
        r'\(entity\s*:\s*(.*?)\s*:\s*(.*?)\s*:\s*(.*?)\s*:\s*(.*?)\s*\)'
    )
    REL_PATTERN = re.compile(
        r'\(relationship\s*:\s*(.*?)\s*:\s*(.*?)\s*:\s*(.*?)\s*:\s*(.*?)\s*:\s*(.*?)\s*\)'
    )

    def __init__(self, similarity_threshold: float = 0.85, min_confidence: float = 0.6):
        """
        Args:
            similarity_threshold: 实体名相似度阈值 [0, 1]，≥ 此值视为同一实体
            min_confidence:       置信度阈值，低于此值的实体/关系被过滤掉
        """
        self.similarity_threshold = similarity_threshold
        self.min_confidence = min_confidence

        # 统计
        self.stats = {
            "total_entities": 0,
            "total_relationships": 0,
            "filtered_by_confidence": 0,
            "merged_entities": 0,
            "removed_self_rels": 0,
            "removed_dup_rels": 0,
        }

    # ------------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------------

    def deduplicate(
        self,
        file_contents: List[Tuple[str, list, list]],
    ) -> List[Tuple[str, list, list]]:
        """
        对 entity_extractor 的输出做全量去重。

        Args:
            file_contents: entity_extractor 的输出
                [(file_name, [Chunk, ...], [LLM结果字符串, ...]), ...]

        Returns:
            同格式，LLM 结果字符串中的重复实体和关系已被合并
        """
        if not file_contents:
            return file_contents

        # ---- 第一遍：解析所有 LLM 字符串 ----
        all_entities: Dict[str, dict] = {}       # name → {type, desc, confidence_max, count}
        all_relationships: List[dict] = []        # [{src, tgt, rel_type, desc, confidence}]

        for _file_name, _chunks, llm_results in file_contents:
            for result in llm_results:
                if not result or not isinstance(result, str):
                    continue
                self._parse_entities(result, all_entities)
                self._parse_relationships(result, all_relationships)

        self.stats["total_entities"] = len(all_entities)
        self.stats["total_relationships"] = len(all_relationships)

        # ---- 第二遍：按置信度过滤 ----
        all_entities = self._filter_by_confidence(all_entities)

        # ---- 第三遍：聚类去重 ----
        name_mapping, canonical_entities = self._cluster_entities(all_entities)

        self.stats["merged_entities"] = len(name_mapping)

        if not name_mapping:
            # 没有重复，原样返回
            return file_contents

        # ---- 第四遍：将映射应用到每个 LLM 字符串 ----
        deduplicated: List[Tuple[str, list, list]] = []
        for file_name, chunks, llm_results in file_contents:
            new_results = [
                self._apply_mapping(result, name_mapping, canonical_entities)
                for result in llm_results
            ]
            deduplicated.append((file_name, chunks, new_results))

        return deduplicated

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    def _parse_entities(self, text: str, entities: Dict[str, dict]) -> None:
        """从单条 LLM 结果字符串中提取实体，合并到全局 entities 字典。"""
        for match in self.NODE_PATTERN.finditer(text):
            raw_name, raw_type, raw_desc, raw_conf = (
                g.strip('"\' ') for g in match.groups()
            )
            try:
                conf = float(raw_conf)
            except ValueError:
                conf = 0.5
            conf = max(0.0, min(1.0, conf))

            if raw_name not in entities:
                entities[raw_name] = {
                    "type": raw_type,
                    "desc": raw_desc,
                    "confidence_max": conf,
                    "count": 0,
                }
            entities[raw_name]["count"] += 1
            # 保留更长的描述
            if len(raw_desc) > len(entities[raw_name]["desc"]):
                entities[raw_name]["desc"] = raw_desc
            # 保留最高置信度
            if conf > entities[raw_name]["confidence_max"]:
                entities[raw_name]["confidence_max"] = conf

    def _parse_relationships(self, text: str, relationships: List[dict]) -> None:
        """从单条 LLM 结果字符串中提取关系，追加到全局 relationships 列表。"""
        for match in self.REL_PATTERN.finditer(text):
            src, tgt, rel_type, desc, raw_conf = (
                g.strip('"\' ') for g in match.groups()
            )
            try:
                conf = float(raw_conf)
            except ValueError:
                conf = 0.5
            conf = max(0.0, min(1.0, conf))

            if conf < self.min_confidence:
                self.stats["filtered_by_confidence"] += 1
                continue

            relationships.append({
                "src": src,
                "tgt": tgt,
                "rel_type": rel_type,
                "desc": desc,
                "confidence": conf,
            })

    def _filter_by_confidence(self, entities: Dict[str, dict]) -> Dict[str, dict]:
        """过滤掉置信度低于阈值的实体。"""
        filtered = {}
        for name, info in entities.items():
            if info.get("confidence_max", 0) >= self.min_confidence:
                filtered[name] = info
            else:
                self.stats["filtered_by_confidence"] += 1
                # 统计中去除被过滤的
                self.stats["total_entities"] -= 1
        return filtered

    # ------------------------------------------------------------------
    # 聚类
    # ------------------------------------------------------------------

    def _cluster_entities(
        self,
        entities: Dict[str, dict],
    ) -> Tuple[Dict[str, str], Dict[str, dict]]:
        """
        按 type 分组，组内做 name 模糊聚类。

        Returns:
            name_mapping:       old_name → canonical_name
            canonical_entities: canonical_name → {type, desc, count}（含合并后的信息）
        """
        name_mapping: Dict[str, str] = {}
        canonical_entities: Dict[str, dict] = {}

        # 按 type 分组
        groups: Dict[str, List[str]] = defaultdict(list)
        for name, info in entities.items():
            groups[info["type"]].append(name)

        for etype, names in groups.items():
            if len(names) < 2:
                for n in names:
                    if n not in canonical_entities:
                        canonical_entities[n] = dict(entities[n])
                continue

            clusters = self._cluster_names(names)
            for cluster in clusters:
                if len(cluster) < 2:
                    n = cluster[0]
                    if n not in canonical_entities:
                        canonical_entities[n] = dict(entities[n])
                    continue

                # 选规范名：count 优先 > desc 长度次之
                canonical = max(
                    cluster,
                    key=lambda n: (
                        entities[n]["count"],
                        len(entities[n].get("desc", "")),
                    ),
                )

                merged_info = {
                    "type": etype,
                    "desc": entities[canonical].get("desc", ""),
                    "count": 0,
                    "confidence_max": 0.0,
                }
                for name in cluster:
                    merged_info["count"] += entities[name]["count"]
                    if len(entities[name].get("desc", "")) > len(merged_info["desc"]):
                        merged_info["desc"] = entities[name]["desc"]
                    merged_info["confidence_max"] = max(
                        merged_info["confidence_max"],
                        entities[name].get("confidence_max", 0),
                    )

                canonical_entities[canonical] = merged_info

                for name in cluster:
                    if name != canonical:
                        name_mapping[name] = canonical

        return name_mapping, canonical_entities

    def _cluster_names(self, names: List[str]) -> List[List[str]]:
        """
        基于字符串相似度做聚类（并查集）。
        仅使用 SequenceMatcher.ratio() ≥ similarity_threshold 判定为同类。
        """
        parent = {n: n for n in names}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            parent[find(x)] = find(y)

        for i in range(len(names)):
            a = names[i]
            for j in range(i + 1, len(names)):
                b = names[j]
                ratio = SequenceMatcher(None, a, b).ratio()
                if ratio >= self.similarity_threshold:
                    union(a, b)

        clusters: Dict[str, List[str]] = defaultdict(list)
        for name in names:
            clusters[find(name)].append(name)

        return list(clusters.values())

    # ------------------------------------------------------------------
    # 重写
    # ------------------------------------------------------------------

    def _apply_mapping(
        self,
        text: str,
        name_mapping: Dict[str, str],
        canonical_entities: Dict[str, dict],
    ) -> str:
        """
        将映射表应用到单条 LLM 结果字符串。
        输出格式保持与输入一致：带置信度字段。
        """
        if not text:
            return text

        lines: List[str] = []
        seen_entities: Set[str] = set()
        seen_rels: Set[Tuple[str, str, str]] = set()

        # -- 实体 --
        for match in self.NODE_PATTERN.finditer(text):
            raw_name, raw_type, raw_desc, raw_conf = (
                g.strip('"\' ') for g in match.groups()
            )
            canonical = name_mapping.get(raw_name, raw_name)

            if canonical in seen_entities:
                continue
            seen_entities.add(canonical)

            if canonical in canonical_entities:
                display_desc = canonical_entities[canonical].get("desc", raw_desc)
            else:
                display_desc = raw_desc

            lines.append(
                f'(entity : {canonical} : {raw_type} : {display_desc} : {raw_conf})'
            )

        # -- 关系 --
        for match in self.REL_PATTERN.finditer(text):
            src, tgt, rel_type, desc, raw_conf = (
                g.strip('"\' ') for g in match.groups()
            )
            src = name_mapping.get(src, src)
            tgt = name_mapping.get(tgt, tgt)

            if src == tgt:
                self.stats["removed_self_rels"] += 1
                continue

            rel_key = (src, tgt, rel_type)
            if rel_key in seen_rels:
                self.stats["removed_dup_rels"] += 1
                continue
            seen_rels.add(rel_key)

            lines.append(
                f'(relationship : {src} : {tgt} : {rel_type} : {desc} : {raw_conf})'
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def print_stats(self) -> None:
        """打印去重统计信息。"""
        print(f"[去重统计]")
        print(f"  解析到实体数:              {self.stats['total_entities']}")
        print(f"  解析到关系数:              {self.stats['total_relationships']}")
        print(f"  置信度过滤掉的实体/关系数:  {self.stats['filtered_by_confidence']}")
        print(f"  被合并的重复实体:          {self.stats['merged_entities']}")
        print(f"  移除的自引用关系:          {self.stats['removed_self_rels']}")
        print(f"  移除的重复关系:            {self.stats['removed_dup_rels']}")
