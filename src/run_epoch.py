"""
主流程协调器：一键跑完一个 epoch 的完整流程
用法：
  python src/run_epoch.py --epoch 1          # 跑 epoch_001
  python src/run_epoch.py --epoch 1 --update # 跑完后自动生成 epoch_002 prompt
  python src/run_epoch.py --all --epochs 2   # 连续跑2轮（含自动更新）
  python src/run_epoch.py --analyze          # 只跑 TrueQuestionAnalyzerAgent
"""
import argparse
import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

BASE = os.path.join(os.path.dirname(__file__), "..")


def check_data():
    test_path = os.path.join(BASE, "data/processed/true_definition_judgement_test.jsonl")
    if not os.path.exists(test_path):
        print("ERROR: 找不到 test 集，请先运行数据收集和清洗")
        return False
    count = sum(1 for line in open(test_path, encoding="utf-8") if line.strip())
    if count == 0:
        print("ERROR: test 集为空")
        return False
    print(f"  test 集: {count} 道题 ✓")
    return True


def run_analyze():
    """Agent 2: TrueQuestionAnalyzerAgent"""
    style_path = os.path.join(BASE, "data/processed/style_summary.json")
    if os.path.exists(style_path):
        print("  风格分析已存在，跳过（删除 data/processed/style_summary.json 可重新生成）")
        return True
    print("\n[Agent 2] 分析真题风格...")
    from analyze_true_questions import analyze
    train_path = os.path.join(BASE, "data/processed/true_definition_judgement_train.jsonl")
    analyze(train_path, style_path)
    return True


def run_epoch(epoch: int, n_questions: int = 10, pairwise: int = 3):
    print(f"\n{'='*50}")
    print(f"  EPOCH {epoch:03d} 开始")
    print(f"{'='*50}")

    # Step 1: 生成题目（Agent 3: GeneratorAgent）
    print(f"\n[1/5] 生成 {n_questions} 道题...")
    from generate_questions import generate, save
    questions = generate(epoch, n_questions)
    if not questions:
        print("ERROR: 生成失败")
        return False
    save(questions, epoch)

    # Step 2: 自检（self_check_prompt）
    print(f"\n[2/5] 自检生成题质量...")
    from self_check import self_check
    check_results = self_check(epoch)

    # Step 3: 盲做检查
    print(f"\n[3/5] 盲做检查...")
    from blind_solve import blind_solve
    blind_results = blind_solve(epoch)

    # Step 4: Pairwise 评价（Agent 4: EvaluatorAgent）
    print(f"\n[4/5] Pairwise 评价 (每题对比 {pairwise} 道真题)...")
    from evaluate_pairwise import evaluate
    summary, eval_results = evaluate(epoch, pairwise)

    # Step 5: 输出简报
    n_pass = sum(1 for r in check_results if r.get("pass", True))
    n_consistent = sum(1 for r in blind_results if r["consistent"])
    avg_score = sum(r.get("score", 0) for r in check_results) / len(check_results) if check_results else 0

    print(f"\n[5/5] Epoch {epoch:03d} 完成")
    print(f"  自检通过率:   {n_pass}/{len(check_results)}  平均分: {avg_score:.1f}")
    print(f"  盲做一致性:   {n_consistent}/{len(blind_results)}")
    print(f"  Win Rate:     {summary['win_rate']:.4f}  (W{summary['win']}/T{summary['tie']}/L{summary['loss']})")

    return True


def run_all(start_epoch: int = 1, total_epochs: int = 2, n_questions: int = 10, pairwise: int = 3):
    # 第一轮前先跑 TrueQuestionAnalyzerAgent
    run_analyze()

    results = []
    for i in range(total_epochs):
        epoch = start_epoch + i

        prompt_dir = os.path.join(BASE, f"prompts/epoch_{epoch:03d}")
        if not os.path.exists(prompt_dir):
            print(f"ERROR: prompts/epoch_{epoch:03d}/ 不存在")
            break

        success = run_epoch(epoch, n_questions, pairwise)
        if not success:
            break

        summary_path = os.path.join(BASE, f"runs/epoch_{epoch:03d}/win_rate_summary.json")
        with open(summary_path, encoding="utf-8") as f:
            results.append(json.load(f))

        if i < total_epochs - 1:
            print(f"\n[UPDATE] 自动生成 epoch_{epoch+1:03d} 的 prompt...")
            from update_prompts import update
            update(epoch)

    # 最终对比
    if len(results) >= 2:
        print(f"\n{'='*50}")
        print("  多轮对比汇总")
        print(f"{'='*50}")
        for r in results:
            print(f"  Epoch {r['epoch']:03d}: win_rate={r['win_rate']:.4f}  (W{r['win']}/T{r['tie']}/L{r['loss']})")
        improvement = results[-1]["win_rate"] - results[0]["win_rate"]
        print(f"\n  Win Rate 变化: {results[0]['win_rate']:.4f} → {results[-1]['win_rate']:.4f}  ({improvement:+.4f})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch", type=int, default=1)
    parser.add_argument("--n", type=int, default=10, help="每轮生成题目数")
    parser.add_argument("--pairwise", type=int, default=3, help="每题对比真题数")
    parser.add_argument("--update", action="store_true", help="跑完后自动生成下一轮 prompt")
    parser.add_argument("--all", action="store_true", help="连续跑多轮")
    parser.add_argument("--epochs", type=int, default=2, help="连续跑几轮")
    parser.add_argument("--analyze", action="store_true", help="只运行 TrueQuestionAnalyzerAgent")
    args = parser.parse_args()

    if not check_data():
        sys.exit(1)

    if args.analyze:
        run_analyze()
    elif args.all:
        run_all(args.epoch, args.epochs, args.n, args.pairwise)
    else:
        # 单轮前也先检查风格分析是否存在
        run_analyze()
        success = run_epoch(args.epoch, args.n, args.pairwise)
        if success and args.update:
            print(f"\n[UPDATE] 自动生成 epoch_{args.epoch+1:03d} 的 prompt...")
            from update_prompts import update
            update(args.epoch)
