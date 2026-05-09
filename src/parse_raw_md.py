"""
从脏的原始 MD 文件中提取真实定义判断题，其余全部丢弃。
判断标准：必须有完整定义文本 + 选项 ABCD + 答案，且定义来自具体概念（非方法论题）。
"""
import json
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils.model_client import chat

BASE = os.path.join(os.path.dirname(__file__), "..")

EXTRACT_SYSTEM = """你是一个严格的数据清洗专家，专门处理公务员行测定义判断题。

你的任务：从给定文本中提取【真实的定义判断题】。

【真实定义判断题的判断标准】，必须同时满足：
1. 有一段完整的"定义文本"（定义某个具体概念，如"慢病自我管理是指..."）
2. 有"根据上述定义，下列属于/不属于 XX 的是"这样的问句
3. 有完整的 ABCD 四个选项，每个选项是具体场景描述
4. 有明确的正确答案（A/B/C/D）

【以下一律丢弃，不要提取】：
- 时事政治题、常识判断题、逻辑推理题
- 关于"定义判断方法论"的题（如"下列不属于定义判断核心考查要素的是"）
- 选项是"是/否"或纯概念词而非场景描述的题
- 缺少定义文本或缺少答案的题
- 任何不确定是否为真实考题的内容

输出格式（JSON数组，没有真题则返回 []）：
[
  {
    "definition_text": "完整的定义原文...",
    "question_stem": "根据上述定义，下列属于XX的是：",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "D",
    "explanation": "解析原文（如有）",
    "ask_type": "属于",
    "source_hint": "能识别的来源信息，如'24国考副省级'"
  }
]

只输出 JSON，不要任何其他文字。"""


def chunk_text(text: str, chunk_size: int = 3000, overlap: int = 800) -> list[str]:
    """按字符数分块，overlap 足够大确保题目不被截断"""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += chunk_size - overlap
    return chunks


def extract_from_chunk(chunk: str) -> list[dict]:
    try:
        result = chat("evaluator", EXTRACT_SYSTEM, chunk, temperature=0.1)
        start = result.find("[")
        end = result.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        return json.loads(result[start:end])
    except Exception as e:
        print(f"    解析失败: {e}")
        return []


def deduplicate(questions: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for q in questions:
        key = q.get("definition_text", "")[:40]
        if key and key not in seen:
            seen.add(key)
            result.append(q)
    return result


def parse(md_path: str, output_path: str):
    with open(md_path, encoding="utf-8") as f:
        text = f.read()

    chunks = chunk_text(text, chunk_size=4000, overlap=600)
    print(f"文件共 {len(text)} 字，分为 {len(chunks)} 个块处理")

    all_questions = []
    today = datetime.date.today().isoformat()

    for i, chunk in enumerate(chunks):
        print(f"  处理块 {i+1}/{len(chunks)}...", end=" ", flush=True)
        questions = extract_from_chunk(chunk)
        print(f"提取到 {len(questions)} 道")
        all_questions.extend(questions)

    all_questions = deduplicate(all_questions)
    print(f"\n去重后共 {len(all_questions)} 道真实定义判断题")

    # 补充元数据
    for i, q in enumerate(all_questions):
        q["id"] = f"true_{i+1:03d}"
        q["source_url"] = "手动收集"
        q["source_name"] = q.pop("source_hint", "未知来源")
        q["retrieved_at"] = today
        q["exam_year"] = "未知"
        q["exam_type"] = "国考/省考"
        q["paper_type"] = "未知"
        q["question_type"] = "定义判断"
        q["tags"] = []
        q["source_quality"] = "ok"
        q["answer_confidence"] = "ok"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for q in all_questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"已保存到 {output_path}")
    return all_questions


if __name__ == "__main__":
    md_path = os.path.join(BASE, "data/raw/collected_raw.md")
    output_path = os.path.join(BASE, "data/raw/raw_questions.jsonl")
    parse(md_path, output_path)
