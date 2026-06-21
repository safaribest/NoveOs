"""StyleSkillRetriever —— 向量检索器（TF-IDF + FAISS）。

从 novel-style-db 的 33 本小说 SKILL.md 中构建 FAISS 索引，
按品类+场景类型语义检索匹配的写作技法+片段。

用法：
    # 构建索引
    python -m core.style_retriever --build

    # 运行时查询
    retriever = StyleSkillRetriever()
    results = retriever.query("玄幻", "战斗", top_k=3)
"""

from __future__ import annotations

import json
import logging
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("novel-os.style_retriever")

# 索引存储路径
_INDEX_DIR = Path(__file__).parent / ".style_index"
_INDEX_FILE = _INDEX_DIR / "style_index.faiss"
_META_FILE = _INDEX_DIR / "style_metadata.json"
_VEC_FILE = _INDEX_DIR / "vectorizer.pkl"

# novel-style-db 根目录（项目内）
_NOVEL_DB_ROOT = Path(__file__).parent.parent.parent / ".claude" / "skills" / "novel-style-db"


@dataclass
class StyleChunk:
    """一个风格片段。"""
    id: str
    genre: str
    novel: str
    scene_type: str
    content: str
    char_count: int


def _classify_scene_type(text: str) -> str:
    """根据内容推断场景类型。"""
    combined = text
    if any(kw in combined for kw in ["战斗", "打斗", "武技", "招式", "拳", "剑", "刀", "锤", "锻打", "击"]):
        return "战斗"
    if any(kw in combined for kw in ["对话", "说", "道", "骂", "喊", "交谈", "问答", "反问", "对话标签"]):
        return "对话"
    if any(kw in combined for kw in ["描写", "动作流", "微观", "肢解", "画面感", "感官", "视觉", "气味", "环境"]):
        return "描写"
    if any(kw in combined for kw in ["情绪", "情感", "怒", "悲", "喜", "恐", "惧", "哭泣", "发抖", "标注"]):
        return "情绪"
    if any(kw in combined for kw in ["设定", "规则", "系统", "世界", "等级", "体系", "递进", "魂", "境", "解锁"]):
        return "设定"
    return "综合"


def _parse_skill_md(filepath: Path) -> dict[str, str]:
    """解析 SKILL.md，提取各节内容。"""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return {}

    sections: dict[str, str] = {}
    current_heading = "header"
    current_lines: list[str] = []

    for line in content.split("\n"):
        if line.startswith("## ") and not line.startswith("### "):
            if current_lines:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def build_index(progress_callback=None) -> tuple[int, int]:
    """构建 TF-IDF + FAISS 索引。

    Returns:
        (chunk_count, dimension)
    """
    import faiss
    from sklearn.feature_extraction.text import TfidfVectorizer

    _INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 解析所有小说 SKILL.md → chunks
    chunks: list[StyleChunk] = []
    for genre_dir in sorted(_NOVEL_DB_ROOT.iterdir()):
        if not genre_dir.is_dir():
            continue
        genre = genre_dir.name
        for novel_dir in sorted(genre_dir.iterdir()):
            if not novel_dir.is_dir():
                continue
            skill_md = novel_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            novel_name = novel_dir.name
            sections = _parse_skill_md(skill_md)
            if not sections:
                continue

            # Chunk 1: 风格DNA → 综合
            if "风格DNA" in sections:
                chunks.append(StyleChunk(
                    id=f"{genre}/{novel_name}/dna",
                    genre=genre, novel=novel_name, scene_type="综合",
                    content=sections["风格DNA"][:500],
                    char_count=len(sections["风格DNA"][:500]),
                ))

            # Chunk 2: 核心技法 → 按场景分类
            if "核心技法" in sections:
                tech_text = sections["核心技法"]
                techniques = re.split(r"\n(?=###?\s+\d+[\.\s])", tech_text)
                for tech in techniques:
                    tech = tech.strip()
                    if not tech or len(tech) < 30:
                        continue
                    chunks.append(StyleChunk(
                        id=f"{genre}/{novel_name}/tech/{len(chunks)}",
                        genre=genre, novel=novel_name,
                        scene_type=_classify_scene_type(tech),
                        content=tech[:600],
                        char_count=len(tech[:600]),
                    ))

            # Chunk 3: 代表性片段 → 按场景分类
            if "代表性片段" in sections:
                excerpt_text = sections["代表性片段"]
                fragments = re.split(r"\n(?=###\s+片段\d+)", excerpt_text)
                for frag in fragments:
                    frag = frag.strip()
                    if not frag or len(frag) < 30:
                        continue
                    chunks.append(StyleChunk(
                        id=f"{genre}/{novel_name}/excerpt/{len(chunks)}",
                        genre=genre, novel=novel_name,
                        scene_type=_classify_scene_type(frag),
                        content=frag[:500],
                        char_count=len(frag[:500]),
                    ))

            # Chunk 4: 语汇特征 → 对话/综合
            if "语汇特征" in sections:
                vocab = sections["语汇特征"]
                st = "对话" if "对话标签" in vocab else "综合"
                chunks.append(StyleChunk(
                    id=f"{genre}/{novel_name}/vocab",
                    genre=genre, novel=novel_name, scene_type=st,
                    content=vocab[:400],
                    char_count=len(vocab[:400]),
                ))

            if progress_callback:
                progress_callback(genre, novel_name, len(chunks))

    logger.info("共解析 %d 个 chunks", len(chunks))

    # 2. TF-IDF 向量化
    #    在内容前附加品类名称以增强品类相关性
    texts = [f"{c.genre} {c.scene_type} {c.content}" for c in chunks]
    vectorizer = TfidfVectorizer(
        max_features=1024,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform(texts)
    embeddings = tfidf_matrix.toarray().astype("float32")

    # L2 归一化 → 内积 = 余弦相似度
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    embeddings = embeddings / norms

    dim = embeddings.shape[1]
    logger.info("TF-IDF 向量化完成: %d vectors, dim=%d", len(chunks), dim)

    # 3. 构建 FAISS 索引
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    logger.info("FAISS 索引完成: %d vectors", index.ntotal)

    # 4. 保存
    faiss.write_index(index, str(_INDEX_FILE))
    with open(_VEC_FILE, "wb") as f:
        pickle.dump(vectorizer, f)

    metadata = {
        "chunks": [
            {
                "id": c.id,
                "genre": c.genre,
                "novel": c.novel,
                "scene_type": c.scene_type,
                "content": c.content,
                "char_count": c.char_count,
            }
            for c in chunks
        ],
        "dim": dim,
        "total_chunks": len(chunks),
        "embedding_type": "tfidf",
    }
    _META_FILE.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("索引已保存: %s / %s / %s", _INDEX_FILE, _META_FILE, _VEC_FILE)

    return len(chunks), dim


class StyleSkillRetriever:
    """风格技能向量检索器。"""

    def __init__(self):
        self._index = None
        self._metadata = None
        self._vectorizer = None
        self._loaded = False

    @property
    def is_available(self) -> bool:
        return _INDEX_FILE.exists() and _META_FILE.exists() and _VEC_FILE.exists()

    def _ensure_loaded(self):
        if self._loaded:
            return
        if not self.is_available:
            raise FileNotFoundError(
                "索引不存在，请先运行: python -m core.style_retriever --build"
            )

        import faiss

        self._index = faiss.read_index(str(_INDEX_FILE))
        self._metadata = json.loads(_META_FILE.read_text(encoding="utf-8"))
        with open(_VEC_FILE, "rb") as f:
            self._vectorizer = pickle.load(f)
        self._loaded = True
        logger.info(
            "StyleSkillRetriever 已加载: %d chunks, dim=%d",
            self._index.ntotal, self._metadata["dim"],
        )

    def query(
        self,
        genre: str = "",
        scene_type: str = "综合",
        scene_description: str = "",
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """检索匹配的风格片段。"""
        self._ensure_loaded()

        # 构建查询文本（附加品类权重）
        query_text = f"{genre} {scene_type} {scene_description[:200]}"

        # TF-IDF 向量化
        query_vec = self._vectorizer.transform([query_text]).toarray().astype("float32")
        norms = np.linalg.norm(query_vec, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        query_vec = query_vec / norms

        # FAISS 检索（取 top_k*4 然后过滤）
        scores, indices = self._index.search(query_vec, top_k * 4)

        # 按品类+场景过滤排序
        results = []
        chunks = self._metadata["chunks"]
        genre_family = _GENRE_FAMILY.get(genre, set()) | {genre}

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(chunks):
                continue
            chunk = chunks[idx]
            chunk_genre = chunk.get("genre", "")

            # 品类匹配
            if chunk_genre not in genre_family:
                continue

            # 场景类型加分（精确匹配 + 30%）
            adjusted_score = float(score)
            if chunk.get("scene_type") == scene_type:
                adjusted_score *= 1.3

            results.append({
                "content": chunk.get("content", ""),
                "novel": chunk.get("novel", ""),
                "genre": chunk_genre,
                "scene_type": chunk.get("scene_type", ""),
                "score": adjusted_score,
            })

        # 按调整后分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]

        # 如果品类内不够，跨品类补充
        if len(results) < top_k:
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(chunks):
                    continue
                chunk = chunks[idx]
                if any(r["content"] == chunk.get("content", "") for r in results):
                    continue
                results.append({
                    "content": chunk.get("content", ""),
                    "novel": chunk.get("novel", ""),
                    "genre": chunk.get("genre", ""),
                    "scene_type": chunk.get("scene_type", ""),
                    "score": float(score),
                })
                if len(results) >= top_k:
                    break

        return results

    def query_for_prompt(
        self,
        genre: str = "",
        scene_type: str = "综合",
        scene_description: str = "",
        top_k: int = 3,
        max_chars: int = 1500,
    ) -> str:
        """检索并格式化为可直接注入 prompt 的文本。"""
        results = self.query(genre, scene_type, scene_description, top_k)

        if not results:
            return ""

        lines: list[str] = []
        total = 0
        for r in results:
            block = (
                f"\n### 参考：《{r['novel']}》"
                f"（{r['genre']}·{r['scene_type']}·相似度{r['score']:.2f}）\n"
                f"{r['content'][:400]}"
            )
            if total + len(block) > max_chars:
                break
            lines.append(block)
            total += len(block)

        return "\n".join(lines)


# 品类族映射（同族互相参考）
_GENRE_FAMILY: dict[str, set[str]] = {
    "玄幻": {"仙侠", "武侠", "奇幻"},
    "仙侠": {"玄幻", "武侠"},
    "武侠": {"玄幻", "仙侠"},
    "都市": {"都市重生", "现言", "穿越"},
    "都市重生": {"都市", "穿越"},
    "言情": {"现言", "古言", "腹黑", "美文"},
    "现言": {"言情", "腹黑"},
    "古言": {"言情", "穿越"},
    "悬疑": {"恐怖", "盗墓", "军事"},
    "恐怖": {"悬疑", "盗墓"},
    "系统流": {"科幻", "网游", "竞技"},
    "科幻": {"系统流", "网游"},
    "网游": {"系统流", "科幻", "竞技"},
    "竞技": {"系统流", "网游"},
    "穿越": {"都市", "历史", "古言"},
    "历史": {"穿越", "军事"},
    "军事": {"历史", "悬疑"},
    "腹黑": {"言情", "美文"},
    "美文": {"言情", "腹黑"},
}


# ─── CLI ───
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if "--build" in sys.argv:
        count, dim = build_index()
        print(f"\n[OK] 索引构建完成: {count} chunks, dim={dim}")
    elif "--test" in sys.argv:
        r = StyleSkillRetriever()
        if not r.is_available:
            print("索引不存在，请先用 --build 构建")
            sys.exit(1)
        tests = [
            ("玄幻", "战斗", "主角施展武技"),
            ("玄幻", "对话", "角色之间交谈"),
            ("都市", "情绪", "主角感到愤怒"),
            ("悬疑", "描写", "恐怖氛围营造"),
            ("言情", "对话", "男女主对话"),
        ]
        for genre, stype, desc in tests:
            print(f"\n=== {genre} / {stype} ({desc}) ===")
            results = r.query(genre, stype, desc, top_k=2)
            for r2 in results:
                print(f"  [{r2['novel']}] ({r2['genre']}·{r2['scene_type']}) score={r2['score']:.3f}")
                print(f"    {r2['content'][:120]}...")
    else:
        print("用法:")
        print("  python -m core.style_retriever --build   # 构建索引")
        print("  python -m core.style_retriever --test    # 测试检索")
