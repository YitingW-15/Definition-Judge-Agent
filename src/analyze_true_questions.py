"""
Agent 2: TrueQuestionAnalyzerAgent
分析真题风格，输出结构化风格摘要，用于指导 Generator 初始化。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils.model_client import chat

BASE = os.path.join(os.path.dirname(__file__), "..")

ANALYZER_SYSTEM = """你是一名资深公务员行测命题研究员，擅长分析定义判断题的命题规律。

你将收到一批真实的定义判断题，请从中提炼出系统性的命题规律。

必须重点分析以下维度：
1. 真题定义通常包含哪些判定要件类型（主体限定/对象限定/方式限定/目的限定/原因限定/结果限定/条件限定/范围限定/排除性限定）
2. 正确选项如何满足全部核心要件
3. 干扰项通常在哪个要件上做手脚（主体错位/目的错位/方式错位/条件缺失/局部符合等）
4. 选是题和选非题的比例
5. 选项长度、语体、场景复杂度的特征
6. 哪些类型的定义具有命题价值，哪些不适合命题
7. 第一眼不容易秒选的题有什么共同特征

严格按照以下 JSON 格式输出，不要有其他文字：
{
  "definition_judgement_style_summary": {
    "common_ask_types": ["选是题（下列属于XX的是）占比约XX%", "选非题（下列不属于XX的是）占比约XX%"],
    "definition_structure_patterns": ["规律1", "规律2", "规律3"],
    "core_criteria_types": {
      "主体限定": "描述及频率",
      "目的限定": "描述及频率",
      "方式限定": "描述及频率",
      "条件限定": "描述及频率",
      "结果限定": "描述及频率",
      "范围限定": "描述及频率"
    },
    "option_design_patterns": ["规律1", "规律2"],
    "distractor_patterns": ["干扰项设计规律1", "干扰项设计规律2", "干扰项设计规律3"],
    "common_failure_avoidance_rules": ["避坑规则1", "避坑规则2", "避坑规则3"],
    "difficulty_features": ["难题特征1", "难题特征2"],
    "high_value_definition_features": ["适合命题的定义特征1", "特征2"],
    "low_value_definition_features": ["不适合命题的定义特征1", "特征2"]
  }
}"""


def load_questions(path: str) -> list[dict]:
    questions = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
    return questions


def format_questions_for_analysis(questions: list[dict]) -> str:
    lines = []
    for i, q in enumerate(questions, 1):
        lines.append(f"【题目{i}】")
        lines.append(f"定义：{q.get('definition_text', '')}")
        lines.append(f"题干：{q.get('question_stem', '')}")
        opts = q.get("options", {})
        for k, v in opts.items():
            lines.append(f"{k}. {v}")
        lines.append(f"答案：{q.get('answer', '')}")
        if q.get("explanation"):
            lines.append(f"解析：{q['explanation'][:200]}")
        lines.append("")
    return "\n".join(lines)


def analyze(train_path: str, output_path: str):
    questions = load_questions(train_path)
    print(f"加载 {len(questions)} 道训练集真题")

    # 分批分析（每批15道），最后合并
    batch_size = 15
    batch_summaries = []

    for i in range(0, len(questions), batch_size):
        batch = questions[i:i + batch_size]
        print(f"  分析第 {i//batch_size + 1} 批（{len(batch)} 道）...")
        formatted = format_questions_for_analysis(batch)
        user_prompt = f"以下是 {len(batch)} 道真实定义判断题，请分析命题规律：\n\n{formatted}"
        result = chat("evaluator", ANALYZER_SYSTEM, user_prompt, temperature=0.2)

        try:
            start = result.find("{")
            end = result.rfind("}") + 1
            summary = json.loads(result[start:end])
            batch_summaries.append(summary)
        except Exception as e:
            print(f"    解析失败: {e}")

    # 如果只有一批，直接用；多批则再合并一次
    if len(batch_summaries) == 1:
        final_summary = batch_summaries[0]
    elif len(batch_summaries) > 1:
        print("  合并多批分析结果...")
        merge_prompt = (
            "以下是对同一批真题分批分析得到的多份风格摘要，请综合合并为一份完整准确的摘要：\n\n"
            + "\n\n".join(json.dumps(s, ensure_ascii=False, indent=2) for s in batch_summaries)
        )
        result = chat("evaluator", ANALYZER_SYSTEM, merge_prompt, temperature=0.2)
        try:
            start = result.find("{")
            end = result.rfind("}") + 1
            final_summary = json.loads(result[start:end])
        except Exception:
            final_summary = batch_summaries[0]
    else:
        print("ERROR: 未能生成任何分析结果")
        return None

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_summary, f, ensure_ascii=False, indent=2)

    print(f"风格分析已保存: {output_path}")

    # 打印摘要
    summary_data = final_summary.get("definition_judgement_style_summary", {})
    print("\n=== 真题风格摘要 ===")
    print(f"题型分布: {summary_data.get('common_ask_types', [])}")
    print(f"干扰项规律: {summary_data.get('distractor_patterns', [])[:2]}")
    print(f"避坑规则: {summary_data.get('common_failure_avoidance_rules', [])[:2]}")

    return final_summary


if __name__ == "__main__":
    train_path = os.path.join(BASE, "data/processed/true_definition_judgement_train.jsonl")
    output_path = os.path.join(BASE, "data/processed/style_summary.json")
    analyze(train_path, output_path)
