"""
盲做检查：让 DeepSeek 在不看答案的情况下做题，验证答案唯一性
"""
import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))
from utils.model_client import chat

BASE = os.path.join(os.path.dirname(__file__), "..")

BLIND_SYSTEM = """你是一名参加公务员行测考试的考生。请认真阅读以下定义判断题，选出正确答案。

要求：
- 只输出答案字母（A、B、C或D），不要解释
- 如果真的无法判断，输出"?"
"""


def blind_solve_one(q: dict) -> str:
    options_text = "\n".join([f"{k}. {v}" for k, v in q["options"].items()])
    user_prompt = (
        f"定义：{q['definition_text']}\n\n"
        f"{q['question_stem']}\n\n"
        f"{options_text}\n\n"
        f"答案："
    )
    result = chat("blind_solver", BLIND_SYSTEM, user_prompt, temperature=0.1)
    # 提取字母
    for char in result.upper():
        if char in ["A", "B", "C", "D"]:
            return char
    return "?"


def blind_solve(epoch: int):
    gen_path = os.path.join(BASE, f"runs/epoch_{epoch:03d}/generated_questions.jsonl")
    questions = []
    with open(gen_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))

    results = []
    for i, q in enumerate(questions):
        print(f"  盲做 {i+1}/{len(questions)}: {q['id']}")
        blind_answer = blind_solve_one(q)
        correct = q.get("answer", "?")
        consistent = blind_answer == correct

        result = {
            "id": q["id"],
            "correct_answer": correct,
            "blind_answer": blind_answer,
            "consistent": consistent,
        }
        results.append(result)
        print(f"    标注答案: {correct}  盲做答案: {blind_answer}  {'✓' if consistent else '✗'}")

    out_path = os.path.join(BASE, f"runs/epoch_{epoch:03d}/blind_solve_results.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_consistent = sum(1 for r in results if r["consistent"])
    print(f"\n盲做一致性: {n_consistent}/{len(results)} ({n_consistent/len(results)*100:.1f}%)")
    print(f"已保存: {out_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch", type=int, default=1)
    args = parser.parse_args()
    blind_solve(args.epoch)
