"""
EvaluatorAgent：pairwise 对比生成题与真题，计算 win rate
"""
import json
import random
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))
from utils.model_client import chat

BASE = os.path.join(os.path.dirname(__file__), "..")


def load_evaluator_prompt(epoch: int) -> str:
    path = os.path.join(BASE, f"prompts/epoch_{epoch:03d}/evaluator_prompt.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


def format_question(q: dict) -> str:
    opts = "\n".join([f"{k}. {v}" for k, v in q["options"].items()])
    return (
        f"定义：{q['definition_text']}\n\n"
        f"{q['question_stem']}\n\n"
        f"{opts}\n\n"
        f"答案：{q.get('answer', '?')}\n"
        f"解析：{q.get('explanation', '无')}"
    )


def pairwise_compare(gen_q: dict, true_q: dict, epoch: int, swap: bool = False) -> dict:
    """
    swap=True 时交换A/B，减少位置偏差
    """
    prompt_template = load_evaluator_prompt(epoch)

    if not swap:
        q_a, q_b = gen_q, true_q
        a_is_gen = True
    else:
        q_a, q_b = true_q, gen_q
        a_is_gen = False

    prompt = prompt_template.replace("{question_a}", format_question(q_a))
    prompt = prompt.replace("{question_b}", format_question(q_b))

    result_str = chat("evaluator", "你是公务员行测定义判断题质量评价专家。", prompt, temperature=0.2)

    try:
        start = result_str.find("{")
        end = result_str.rfind("}") + 1
        result = json.loads(result_str[start:end])
    except Exception:
        result = {"winner": "tie", "reason": "解析失败", "score_A": 50, "score_B": 50}

    winner_label = result.get("winner", "tie")

    # 映射回 generated/true
    if winner_label == "A":
        winner = "generated" if a_is_gen else "true"
    elif winner_label == "B":
        winner = "true" if a_is_gen else "generated"
    else:
        winner = "tie"

    return {
        "generated_id": gen_q["id"],
        "true_id": true_q.get("id", "?"),
        "winner": winner,
        "reason": result.get("reason", ""),
        "score_generated": result.get("score_A" if a_is_gen else "score_B", 50),
        "score_true": result.get("score_B" if a_is_gen else "score_A", 50),
        "swapped": swap,
    }


def evaluate(epoch: int, pairwise_per_question: int = 3):
    gen_path = os.path.join(BASE, f"runs/epoch_{epoch:03d}/generated_questions.jsonl")
    test_path = os.path.join(BASE, "data/processed/true_definition_judgement_test.jsonl")

    gen_questions = []
    with open(gen_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                gen_questions.append(json.loads(line))

    test_questions = []
    with open(test_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                test_questions.append(json.loads(line))

    if not test_questions:
        print("WARNING: test集为空，使用dev集")
        dev_path = os.path.join(BASE, "data/processed/true_definition_judgement_dev.jsonl")
        with open(dev_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    test_questions.append(json.loads(line))

    print(f"生成题: {len(gen_questions)} 道，真题: {len(test_questions)} 道")

    all_results = []
    win = tie = loss = 0

    for i, gen_q in enumerate(gen_questions):
        # 随机抽取 pairwise_per_question 道真题对比
        sample_true = random.sample(test_questions, min(pairwise_per_question, len(test_questions)))

        for j, true_q in enumerate(sample_true):
            swap = (j % 2 == 1)  # 交替 swap，减少位置偏差
            print(f"  对比 gen_{i+1} vs true_{j+1} (swap={swap})")

            result = pairwise_compare(gen_q, true_q, epoch, swap=swap)
            all_results.append(result)

            if result["winner"] == "generated":
                win += 1
                print(f"    → 生成题胜")
            elif result["winner"] == "tie":
                tie += 1
                print(f"    → 平局")
            else:
                loss += 1
                print(f"    → 真题胜")

    total = win + tie + loss
    win_rate = (win + 0.5 * tie) / total if total > 0 else 0

    summary = {
        "epoch": epoch,
        "total_generated": len(gen_questions),
        "total_comparisons": total,
        "win": win,
        "tie": tie,
        "loss": loss,
        "win_rate": round(win_rate, 4),
    }

    out_dir = os.path.join(BASE, f"runs/epoch_{epoch:03d}")
    with open(os.path.join(out_dir, "pairwise_eval_results.jsonl"), "w", encoding="utf-8") as f:
        for r in all_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(os.path.join(out_dir, "win_rate_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n=== Epoch {epoch} Win Rate: {win_rate:.4f} ===")
    print(f"Win: {win}  Tie: {tie}  Loss: {loss}  Total: {total}")
    return summary, all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch", type=int, default=1)
    parser.add_argument("--pairwise", type=int, default=3)
    args = parser.parse_args()
    evaluate(args.epoch, args.pairwise)
