"""
清洗数据 + 划分 train/dev/test
"""
import json
import random
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))


REQUIRED_FIELDS = ["definition_text", "question_stem", "options", "answer"]


def is_valid(q: dict) -> tuple[bool, str]:
    for f in REQUIRED_FIELDS:
        if not q.get(f):
            return False, f"缺少字段: {f}"

    opts = q.get("options", {})
    if not all(k in opts for k in ["A", "B", "C", "D"]):
        return False, "选项不完整"

    if q["answer"] not in ["A", "B", "C", "D"]:
        return False, f"答案格式错误: {q['answer']}"

    if len(q.get("definition_text", "")) < 20:
        return False, "定义太短"

    for k, v in opts.items():
        if not v or len(v) < 3:
            return False, f"选项{k}内容为空或太短"

    return True, "ok"


def clean(raw_path: str, cleaned_path: str):
    questions = []
    skipped = 0

    with open(raw_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                q = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            valid, reason = is_valid(q)
            if not valid:
                print(f"  跳过 [{q.get('id', '?')}]: {reason}")
                skipped += 1
                continue

            # 标注低质量
            if not q.get("explanation"):
                q["answer_confidence"] = "low"
            else:
                q["answer_confidence"] = "ok"
            q.setdefault("source_quality", "ok")

            questions.append(q)

    print(f"清洗完成: 保留 {len(questions)} 道，跳过 {skipped} 道")

    os.makedirs(os.path.dirname(cleaned_path), exist_ok=True)
    with open(cleaned_path, "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    return questions


def split(questions: list[dict], out_dir: str, train_r=0.6, dev_r=0.2):
    random.seed(42)
    random.shuffle(questions)

    n = len(questions)
    n_train = int(n * train_r)
    n_dev = int(n * dev_r)

    train = questions[:n_train]
    dev = questions[n_train:n_train + n_dev]
    test = questions[n_train + n_dev:]

    for q in train:
        q["split"] = "train"
    for q in dev:
        q["split"] = "dev"
    for q in test:
        q["split"] = "test"

    os.makedirs(out_dir, exist_ok=True)
    for name, subset in [("train", train), ("dev", dev), ("test", test)]:
        path = os.path.join(out_dir, f"true_definition_judgement_{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for q in subset:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        print(f"  {name}: {len(subset)} 道 → {path}")

    return train, dev, test


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="data/raw/raw_questions.jsonl")
    parser.add_argument("--cleaned", default="data/raw/cleaned_questions.jsonl")
    parser.add_argument("--out_dir", default="data/processed")
    args = parser.parse_args()

    base = os.path.join(os.path.dirname(__file__), "..")
    raw_path = os.path.join(base, args.raw)
    cleaned_path = os.path.join(base, args.cleaned)
    out_dir = os.path.join(base, args.out_dir)

    questions = clean(raw_path, cleaned_path)
    if len(questions) < 10:
        print("WARNING: 数据量太少，请检查爬虫或手动补充数据")
    split(questions, out_dir)
