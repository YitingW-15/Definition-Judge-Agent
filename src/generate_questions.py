"""
GeneratorAgent：读取 generator_prompt.md，生成 N 道定义判断题
"""
import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))
from utils.model_client import chat

BASE = os.path.join(os.path.dirname(__file__), "..")


def load_prompt(epoch: int) -> str:
    path = os.path.join(BASE, f"prompts/epoch_{epoch:03d}/generator_prompt.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


def generate(epoch: int, n: int = 10) -> list[dict]:
    prompt_template = load_prompt(epoch)
    system_prompt = prompt_template.replace("{n}", str(n))

    user_prompt = f"请生成 {n} 道定义判断题，按JSON数组格式输出。"

    print(f"  调用 DeepSeek 生成 {n} 道题...")
    result = chat("generator", system_prompt, user_prompt, temperature=0.8)

    # 提取JSON
    start = result.find("[")
    end = result.rfind("]") + 1
    if start == -1 or end == 0:
        print("  WARNING: 未能解析JSON，尝试提取...")
        print(result[:500])
        return []

    json_str = result[start:end]
    try:
        questions = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"  JSON解析失败: {e}，尝试自动修复...")
        from json_repair import repair_json
        try:
            questions = json.loads(repair_json(json_str))
        except Exception as e2:
            print(f"  修复失败: {e2}")
            questions = []

    # 修正 id
    for i, q in enumerate(questions):
        q["id"] = f"epoch_{epoch:03d}_gen_{i+1:03d}"
        q["epoch"] = epoch

    # 随机打乱选项顺序，避免模型总把正确答案放在固定位置
    import random
    keys = ["A", "B", "C", "D"]
    for q in questions:
        if not q.get("options") or q.get("answer") not in keys:
            continue
        correct_text = q["options"][q["answer"]]
        items = list(q["options"].items())
        random.shuffle(items)
        q["options"] = {keys[i]: v for i, (_, v) in enumerate(items)}
        # 更新答案字母
        for k, v in q["options"].items():
            if v == correct_text:
                q["answer"] = k
                break

    print(f"  成功生成 {len(questions)} 道题")
    return questions


def save(questions: list[dict], epoch: int):
    out_dir = os.path.join(BASE, f"runs/epoch_{epoch:03d}")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "generated_questions.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"  已保存: {path}")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch", type=int, default=1)
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()

    questions = generate(args.epoch, args.n)
    save(questions, args.epoch)
