# 数据来源记录

本文件记录定义判断真题的收集来源及处理流程。

---

## 收集方式说明

由于目标网站（华图、粉笔等）存在反爬或 DNS 解析失败，DataCollectorAgent 的自动爬虫在本次 MVP 中未能运行。
实际采用以下手动流程：

```
网络截图/图片 → 豆包 OCR 提取文字 → 复制至 collected_raw.md → parse_raw_md.py 结构化解析 → 人工清洗
```

---

## 数据来源列表

| 序号 | 来源 | 题目类型 | 收集题数 | 备注 |
|---|---|---|---|---|
| 1 | 2024年国家公务员考试《行政职业能力测验》副省级（第86-90题） | 定义判断 | 5 道 | 题号 24副省-86 至 24副省-90；含慢病自我管理、多级养殖、动态描写法、电力设备、复杂型/多变型消费行为 |
| 2 | 2024年国家公务员考试《行政职业能力测验》行政执法类（第86-90题） | 定义判断 | 5 道 | 含品牌延伸等考点 |
| 3 | 历年省考定义判断散题（2022-2024） | 定义判断 | 约 25 道 | 来源：各省行测真题截图，经豆包 OCR 后批量解析 |
| 4 | 公考定义判断练习题库（网络公开资源） | 定义判断 | 约 15 道 | 部分题目为题库整理，质量参差，清洗时剔除格式错误题 |

**合计收集**：约 50 道（清洗后保留 50 道，跳过 0 道）

---

## 数据划分

| 集合 | 数量 | 文件 | 用途 |
|---|---|---|---|
| Train | 30 道 | `data/processed/true_definition_judgement_train.jsonl` | TrueQuestionAnalyzerAgent 风格分析 |
| Dev | 10 道 | `data/processed/true_definition_judgement_dev.jsonl` | 调试与中间验证 |
| Test | 10 道 | `data/processed/true_definition_judgement_test.jsonl` | Pairwise 评价基准（不参与训练或分析） |

---

## 原始文件

- `data/raw/collected_raw.md`：豆包 OCR 提取的原始文字，包含完整题目、选项、答案及解析（部分题目格式较乱）
- `data/raw/raw_questions.jsonl`：`parse_raw_md.py` 首次解析输出（未清洗）
- `data/raw/cleaned_questions.jsonl`：人工清洗后结果，去除非定义判断题型及格式异常条目

---

## 数据质量说明

- 所有保留题目均为单选四选一格式（ABCD），含定义文本、题干、四个选项、答案字母及解析
- 清洗标准：定义文本长度 ≥ 20 字、选项数量 = 4、答案字母在 ABCD 之间
- 原始 MD 中混有言语理解（成语、逻辑填空）等非目标题型，已在解析阶段过滤

---

## 爬虫代码

`src/collect_data.py` 已实现爬虫框架（基于 requests + BeautifulSoup），目标网站包括：
- 华图公考题库（国考真题频道）
- 粉笔公考（定义判断专项）

待目标网站可访问时可直接接入，无需修改 DataCollectorAgent 下游流程。
