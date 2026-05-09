"""
用 DeepSeek 生成一批高质量参考题作为评价基准（用于 pipeline 调试和 MVP 演示）。
后续可直接用真实数据替换 data/processed/ 下的文件，其余代码不需要改动。
"""
import json
import os
import sys
import random
import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils.model_client import chat

BASE = os.path.join(os.path.dirname(__file__), "..")

BOOTSTRAP_SYSTEM = """你是一名资深的公务员行测命题研究员。
请根据你对历年国考、省考定义判断真题的了解，输出结构化的定义判断题目。

要求：
1. 严格按照真实公务员行测定义判断题的风格和难度
2. 定义来自社会学、心理学、经济学、管理学、法学等领域（不要太常识化）
3. 每道题必须有完整的定义、题干、四个选项、正确答案、解析
4. 答案必须唯一且正确，解析必须基于定义要件
5. 至少包含"选是题"和"选非题"各若干道
6. 干扰项必须有真实迷惑性，不能是废项

输出 JSON 数组，格式如下：
[
  {
    "definition_text": "完整的定义文本...",
    "question_stem": "下列行为中，属于XX的是：",
    "options": {
      "A": "...",
      "B": "...",
      "C": "...",
      "D": "..."
    },
    "answer": "B",
    "explanation": "解析：根据定义，核心要件是...选项B符合...选项A不符合因为...",
    "ask_type": "属于",
    "exam_type": "国考",
    "exam_year": "2023",
    "tags": ["单定义", "选是题", "心理学"]
  }
]

只输出 JSON 数组，不要有任何其他文字。"""


def bootstrap(n_total: int = 60):
    """生成 n_total 道参考题，分批次请求避免超时"""
    batch_size = 15
    n_batches = (n_total + batch_size - 1) // batch_size
    all_questions = []
    today = datetime.date.today().isoformat()

    domains = [
        "社会学、社会心理学领域",
        "经济学、行为经济学领域",
        "管理学、组织行为学领域",
        "法学、行政法领域",
        "心理学、认知科学领域",
    ]

    for i in range(n_batches):
        domain = domains[i % len(domains)]
        n_this = min(batch_size, n_total - len(all_questions))
        print(f"\n[批次 {i+1}/{n_batches}] 生成 {n_this} 道题（{domain}）...")

        user_prompt = (
            f"请生成 {n_this} 道定义判断题，"
            f"定义概念来自{domain}，"
            f"风格严格对标公务员行测真题。"
            f"输出 JSON 数组。"
        )

        result = chat("generator", BOOTSTRAP_SYSTEM, user_prompt, temperature=0.7)

        try:
            start = result.find("[")
            end = result.rfind("]") + 1
            if start == -1 or end == 0:
                print(f"  WARNING: 未解析到JSON")
                continue
            questions = json.loads(result[start:end])
        except json.JSONDecodeError as e:
            print(f"  JSON解析失败: {e}")
            continue

        for j, q in enumerate(questions):
            idx = len(all_questions) + j + 1
            q["id"] = f"ref_{idx:03d}"
            q["source_url"] = "bootstrap_deepseek"
            q["source_name"] = "DeepSeek参考题"
            q["retrieved_at"] = today
            q["paper_type"] = "未知"
            q["question_type"] = "定义判断"
            q.setdefault("tags", [])
            q.setdefault("ask_type", "属于")
            q.setdefault("exam_year", "2023")
            q.setdefault("exam_type", "国考")
            q["source_quality"] = "bootstrap"
            q["answer_confidence"] = "ok"

        all_questions.extend(questions)
        print(f"  本批获得 {len(questions)} 道，累计 {len(all_questions)} 道")

        if len(all_questions) >= n_total:
            break

    # 去重
    seen = set()
    unique = []
    for q in all_questions:
        key = q.get("definition_text", "")[:40]
        if key not in seen:
            seen.add(key)
            unique.append(q)

    print(f"\n去重后共 {len(unique)} 道题")
    return unique


def save_and_split(questions: list, out_dir: str):
    random.seed(42)
    random.shuffle(questions)
    n = len(questions)
    n_train = int(n * 0.6)
    n_dev = int(n * 0.2)

    splits = {
        "train": questions[:n_train],
        "dev": questions[n_train:n_train + n_dev],
        "test": questions[n_train + n_dev:],
    }

    os.makedirs(out_dir, exist_ok=True)
    for name, subset in splits.items():
        for q in subset:
            q["split"] = name
        path = os.path.join(out_dir, f"true_definition_judgement_{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for q in subset:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        print(f"  {name}: {len(subset)} 道 → {path}")

    # 同时保存 raw
    raw_path = os.path.join(BASE, "data/raw/raw_questions.jsonl")
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"  raw: {len(questions)} 道 → {raw_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=60, help="生成题目总数")
    args = parser.parse_args()

    out_dir = os.path.join(BASE, "data/processed")
    questions = bootstrap(args.n)

    if len(questions) < 20:
        print("ERROR: 生成数量太少，请检查API连接")
        sys.exit(1)

    save_and_split(questions, out_dir)
    print(f"\n数据集已就绪，共 {len(questions)} 道参考题")
    print("后续可将 data/processed/ 替换为真实数据，pipeline 无需改动")
