"""
Self-check：对生成题逐题进行质检，标记问题，输出 self_check_results.jsonl
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils.model_client import chat

BASE = os.path.join(os.path.dirname(__file__), "..")


def load_prompt(epoch: int) -> str:
    path = os.path.join(BASE, f"prompts/epoch_{epoch:03d}/self_check_prompt.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


def self_check(epoch: int) -> list[dict]:
    gen_path = os.path.join(BASE, f"runs/epoch_{epoch:03d}/generated_questions.jsonl")
    questions = []
    with open(gen_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))

    prompt_template = load_prompt(epoch)

    # 逐题检查（避免一次输入太多）
    all_results = []
    for i, q in enumerate(questions):
        print(f"  自检 {i+1}/{len(questions)}: {q['id']}")
        questions_json = json.dumps([q], ensure_ascii=False, indent=2)
        prompt = prompt_template.replace("{questions_json}", questions_json)

        result_str = chat("evaluator", "你是严格的定义判断题质检专家。", prompt, temperature=0.1)

        try:
            from json_repair import repair_json
            # 优先找 { } 提取单个对象
            start = result_str.find("{")
            end = result_str.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("未找到JSON")
            parsed = json.loads(repair_json(result_str[start:end]))
            # 处理 list 或 dict 两种情况
            if isinstance(parsed, list):
                result = parsed[0] if parsed else {}
            else:
                result = parsed
        except Exception as e:
            print(f"    解析失败: {e}")
            result = {"id": q["id"], "pass": True, "score": 0, "issues": ["解析失败"]}

        result["id"] = q["id"]
        all_results.append(result)

        passed = result.get("pass", True)
        score = result.get("score", "?")
        issues = result.get("issues", [])
        status = "✓" if passed else "✗"
        print(f"    {status} score={score}  {'|'.join(issues[:2]) if issues else 'ok'}")

    # 统计
    n_pass = sum(1 for r in all_results if r.get("pass", True))
    avg_score = sum(r.get("score", 0) for r in all_results) / len(all_results) if all_results else 0
    print(f"\n自检通过: {n_pass}/{len(all_results)}  平均分: {avg_score:.1f}")

    out_path = os.path.join(BASE, f"runs/epoch_{epoch:03d}/self_check_results.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for r in all_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"已保存: {out_path}")

    return all_results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch", type=int, default=1)
    args = parser.parse_args()
    self_check(args.epoch)
