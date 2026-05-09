"""
UpdaterAgent：根据本轮评估报告，生成下一轮 epoch 的 prompts
"""
import json
import os
import sys
import argparse
import shutil

sys.path.insert(0, os.path.dirname(__file__))
from utils.model_client import chat

BASE = os.path.join(os.path.dirname(__file__), "..")


def build_epoch_report(epoch: int) -> str:
    run_dir = os.path.join(BASE, f"runs/epoch_{epoch:03d}")

    # 加载 win rate
    with open(os.path.join(run_dir, "win_rate_summary.json"), encoding="utf-8") as f:
        summary = json.load(f)

    # 加载 pairwise 结果
    results = []
    with open(os.path.join(run_dir, "pairwise_eval_results.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))

    # 加载盲做结果
    blind_results = []
    blind_path = os.path.join(run_dir, "blind_solve_results.jsonl")
    if os.path.exists(blind_path):
        with open(blind_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    blind_results.append(json.loads(line))

    # 加载生成题
    gen_questions = []
    with open(os.path.join(run_dir, "generated_questions.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                gen_questions.append(json.loads(line))

    # 找出loss的对比
    losses = [r for r in results if r["winner"] == "true"]
    loss_reasons = [r["reason"] for r in losses[:5]]

    blind_consistency = 0
    if blind_results:
        blind_consistency = sum(1 for r in blind_results if r["consistent"]) / len(blind_results)

    report = f"""# Epoch {epoch:03d} 评估报告

## 核心指标
- Win: {summary['win']}
- Tie: {summary['tie']}
- Loss: {summary['loss']}
- Win Rate: {summary['win_rate']}
- 盲做一致性: {blind_consistency:.2%}

## 失败案例分析（前5条loss原因）
"""
    for i, reason in enumerate(loss_reasons, 1):
        report += f"\n### 失败案例 {i}\n{reason}\n"

    report += f"\n## 生成题样例（前3道）\n"
    for q in gen_questions[:3]:
        report += f"\n**{q['id']}**\n"
        report += f"定义：{q.get('definition_text', '')[:100]}...\n"
        report += f"答案：{q.get('answer', '?')}\n"
        notes = q.get('generation_notes', {})
        if notes:
            report += f"要件：{notes.get('core_criteria', [])}\n"

    return report


def update(epoch: int):
    next_epoch = epoch + 1
    next_epoch_dir = os.path.join(BASE, f"prompts/epoch_{next_epoch:03d}")
    os.makedirs(next_epoch_dir, exist_ok=True)

    # 复制上一轮所有 prompt 作为基础
    prev_dir = os.path.join(BASE, f"prompts/epoch_{epoch:03d}")
    for fname in os.listdir(prev_dir):
        shutil.copy(os.path.join(prev_dir, fname), os.path.join(next_epoch_dir, fname))

    # 加载上一轮 generator prompt
    with open(os.path.join(prev_dir, "generator_prompt.md"), encoding="utf-8") as f:
        prev_generator = f.read()

    # 构建 epoch 报告
    epoch_report = build_epoch_report(epoch)
    print("构建评估报告完成")

    # 保存报告
    report_path = os.path.join(BASE, f"runs/epoch_{epoch:03d}/epoch_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(epoch_report)
    print(f"评估报告已保存: {report_path}")

    # 加载 updater prompt
    with open(os.path.join(prev_dir, "updater_prompt.md"), encoding="utf-8") as f:
        updater_template = f.read()

    updater_prompt = updater_template.replace("{prev_generator_prompt}", prev_generator)
    updater_prompt = updater_prompt.replace("{epoch_report}", epoch_report)

    print(f"调用 DeepSeek 生成 epoch_{next_epoch:03d} 的更新策略...")
    result = chat("updater", "你是命题系统架构师。", updater_prompt, temperature=0.4)

    # 提取更新报告和新 prompt
    update_report = result
    new_generator = None

    if "---PROMPT_START---" in result and "---PROMPT_END---" in result:
        parts = result.split("---PROMPT_START---")
        update_report = parts[0].strip()
        new_generator = parts[1].split("---PROMPT_END---")[0].strip()
    else:
        # 尝试直接用结果
        print("  WARNING: 未找到 PROMPT_START/END 标记，使用原始结果")

    # 保存更新报告
    update_report_path = os.path.join(BASE, f"runs/epoch_{epoch:03d}/update_report.md")
    with open(update_report_path, "w", encoding="utf-8") as f:
        f.write(f"# Epoch {epoch:03d} → Epoch {next_epoch:03d} 更新报告\n\n")
        f.write(update_report)
    print(f"更新报告: {update_report_path}")

    # 保存新 generator prompt
    if new_generator:
        new_gen_path = os.path.join(next_epoch_dir, "generator_prompt.md")
        with open(new_gen_path, "w", encoding="utf-8") as f:
            f.write(new_generator)
        print(f"新 Generator Prompt: {new_gen_path}")
    else:
        print("  使用原 generator prompt（未能生成新版本）")

    return next_epoch


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch", type=int, default=1)
    args = parser.parse_args()
    update(args.epoch)
