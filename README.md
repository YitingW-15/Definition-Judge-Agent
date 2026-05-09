# 自进化 AI Agents 定义判断命题系统

基于 DeepSeek API 构建的五 Agent 闭环系统，能够自动生成定义判断题、自检质量、与真题 pairwise 对比评价，并通过 UpdaterAgent 自动改进命题 prompt，实现多轮自进化。

---

## 系统架构

```
DataCollectorAgent → TrueQuestionAnalyzerAgent → GeneratorAgent → EvaluatorAgent → UpdaterAgent
      ↑                                                                                    |
      |____________________________ prompt 更新闭环 ________________________________________|
```

| Agent | 文件 | 职责 |
|---|---|---|
| DataCollectorAgent | `src/parse_raw_md.py` | 解析手动收集的原始题目 MD 文件，结构化为 JSONL |
| TrueQuestionAnalyzerAgent | `src/analyze_true_questions.py` | 分析真题命题规律，输出风格报告 |
| GeneratorAgent | `src/generate_questions.py` | 按 prompt 生成 N 道定义判断题（含自检） |
| EvaluatorAgent | `src/evaluate_pairwise.py` | 与真题 pairwise 对比，计算 win rate |
| UpdaterAgent | `src/update_prompts.py` | 分析失败原因，自动更新下一轮 prompt |

---

## 目录结构

```
definition_judgement_agent/
├── config/
│   ├── models.yaml          # 模型配置（provider、name、temperature）
│   └── experiment.yaml      # 实验参数（每轮题数、pairwise 次数）
├── data/
│   ├── raw/
│   │   ├── collected_raw.md       # 手动收集的原始题目（OCR 提取）
│   │   └── collected_sources.md   # 数据来源记录
│   └── processed/
│       ├── true_definition_judgement_train.jsonl  # 训练集（30 道）
│       ├── true_definition_judgement_dev.jsonl    # 验证集（10 道）
│       ├── true_definition_judgement_test.jsonl   # 测试集（10 道）
│       └── style_summary.json                     # Agent 2 风格分析结果
├── prompts/
│   ├── epoch_001/
│   │   ├── generator_prompt.md    # 命题 prompt
│   │   ├── self_check_prompt.md   # 自检 prompt
│   │   ├── evaluator_prompt.md    # pairwise 评价 prompt
│   │   └── updater_prompt.md      # prompt 更新指令
│   └── epoch_002/                 # UpdaterAgent 自动生成
│       └── generator_prompt.md
├── runs/
│   ├── epoch_001/
│   │   ├── generated_questions.jsonl   # 生成题
│   │   ├── self_check_results.jsonl    # 自检结果
│   │   ├── blind_solve_results.jsonl   # 盲做结果
│   │   ├── pairwise_results.jsonl      # pairwise 对比
│   │   ├── win_rate_summary.json       # win rate 汇总
│   │   └── update_report.md            # UpdaterAgent 更新报告
│   └── epoch_002/
│       └── ...
├── reports/
│   └── final_report.md      # 最终实验报告
├── src/
│   ├── utils/
│   │   └── model_client.py       # DeepSeek API 封装
│   ├── parse_raw_md.py           # DataCollectorAgent
│   ├── analyze_true_questions.py # TrueQuestionAnalyzerAgent
│   ├── generate_questions.py     # GeneratorAgent
│   ├── self_check.py             # 自检模块
│   ├── blind_solve.py            # 盲做检查
│   ├── evaluate_pairwise.py      # EvaluatorAgent
│   ├── update_prompts.py         # UpdaterAgent
│   └── run_epoch.py              # 主流程协调器
├── requirements.txt
└── .env                          # API Key（不提交 git）
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

`requirements.txt` 包含：openai、pyyaml、python-dotenv、json_repair、requests、beautifulsoup4

### 2. 配置 API Key

在项目根目录创建 `.env` 文件：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

> Key 仅在本地读取，不会上传。可在 [DeepSeek 开放平台](https://platform.deepseek.com) 获取。

### 3. 准备真题数据

真题已手动收集并清洗完毕，位于 `data/processed/`。如需重新解析原始 MD：

```bash
python src/parse_raw_md.py
```

### 4. 运行单轮 epoch

```bash
# 运行 epoch_001（生成10题 + 自检 + 盲做 + pairwise）
python src/run_epoch.py --epoch 1

# 运行后自动生成 epoch_002 的 prompt
python src/run_epoch.py --epoch 1 --update
```

### 5. 运行完整多轮自进化

```bash
# 连续跑 2 轮（含 UpdaterAgent 自动更新 prompt）
python src/run_epoch.py --all --epochs 2

# 自定义参数
python src/run_epoch.py --all --epochs 3 --n 10 --pairwise 3
```

参数说明：
- `--n`：每轮生成题目数（默认 10）
- `--pairwise`：每道题对比几道真题（默认 3）
- `--epochs`：连续跑几轮（默认 2）

### 6. 单独运行各模块

```bash
# 只运行 TrueQuestionAnalyzerAgent（分析真题风格）
python src/run_epoch.py --analyze

# 只生成题目
python src/generate_questions.py --epoch 1 --n 10

# 只运行自检
python src/self_check.py --epoch 1

# 只运行 pairwise 评价
python src/evaluate_pairwise.py --epoch 1 --pairwise 3

# 只运行 UpdaterAgent
python src/update_prompts.py --epoch 1
```

### 7. 查看结果

- 各轮详细结果：`runs/epoch_XXX/`
- 最终综合报告：`reports/final_report.md`

---

## 实验结果

| 指标 | Epoch 001 | Epoch 002 | 变化 |
|---|---|---|---|
| Win Rate | 0.2667 | 0.5667 | **+0.3000** |
| 自检通过率 | 30% | 70% | +40% |
| 自检平均分 | 25.6 | 64.0 | +38.4 |
| 盲做一致性 | 100% | 100% | 持平 |

两轮迭代后 Win Rate 提升 30 个百分点，验证了自进化闭环的有效性。

---

## 模型配置

当前配置（`config/models.yaml`）所有角色均使用：

| 参数 | 值 |
|---|---|
| Provider | DeepSeek |
| Model | deepseek-chat（V4-Flash，非思考模式） |
| Base URL | https://api.deepseek.com |

如需切换模型，修改 `config/models.yaml` 中对应角色的 `name` 字段即可。

---

## 注意事项

- `.env` 文件已加入 `.gitignore`，不会提交 API Key
- DataCollectorAgent 的自动爬虫（`src/collect_data.py`）因目标网站 DNS 失败暂不可用，本次数据通过手动收集 + OCR + LLM 解析完成
- pairwise 评估使用 swap 机制（随机互换 A/B 位置）减少位置偏差
- GeneratorAgent 在生成后随机打乱选项顺序，避免答案集中在 A 位
