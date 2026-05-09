"""
DataCollectorAgent
从公开网页抓取定义判断真题，用 DeepSeek 解析 HTML 提取结构化数据。
"""
import json
import time
import hashlib
import datetime
import argparse
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from utils.model_client import chat

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# 公开可访问的定义判断真题页面（纯文字HTML，无需登录）
SEED_URLS = [
    # 中公题库 - 定义判断专项
    "http://www.offcnks.com/xingce/panjuan/dyjudge/",
    # 华图 - 定义判断解析
    "https://www.huatu.com/zt/dingyi/",
    # 粉笔公考 - 真题
    "https://www.fenbi.com/spa/tiku/guide/xingce",
    # 公考雷达 行测定义判断
    "https://gongkaoleida.com/article/xingce/dyjudge",
    # 考虫 - 历年真题
    "https://www.kaochong.com/lnzt/xingce",
]

# 针对具体题库页面的种子（更稳定）
QUESTION_PAGE_URLS = [
    "https://www.360juzi.com/qtype/dingyi/",
    "https://www.ahzsrc.com/xingce/dyjudge.html",
    "https://www.kgongwuyuan.com/xingce/panjuan/dyjudge.html",
    "https://www.chinagwy.org/html/kszx/xingce/panjuan/",
]


EXTRACT_SYSTEM = """你是一个数据提取助手。用户会给你一段网页HTML内容，请从中提取所有"定义判断"题目。

每道题必须包含：
- definition_text: 题目给出的定义文本（完整）
- question_stem: 问句（如"下列属于XX的是"）
- options: {A: ..., B: ..., C: ..., D: ...}
- answer: 正确答案字母（A/B/C/D）
- explanation: 解析（如有）
- ask_type: 选是题填"属于"，选非题填"不属于"，其他类似

如果某道题信息不完整（缺选项、缺答案），直接跳过。

输出格式为JSON数组，不要有多余文字：
[
  {
    "definition_text": "...",
    "question_stem": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A",
    "explanation": "...",
    "ask_type": "属于"
  },
  ...
]

如果没有找到任何定义判断题，返回空数组 []。"""


def fetch_page(url: str, timeout: int = 10) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.encoding = resp.apparent_encoding
        if resp.status_code == 200:
            return resp.text
        print(f"  HTTP {resp.status_code}: {url}")
    except Exception as e:
        print(f"  请求失败: {url} — {e}")
    return None


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    # 只保留前8000字，避免token过多
    return text[:8000]


def llm_extract_questions(page_text: str, source_url: str) -> list[dict]:
    user_prompt = f"来源URL: {source_url}\n\n网页内容:\n{page_text}"
    try:
        result = chat("evaluator", EXTRACT_SYSTEM, user_prompt, temperature=0.1)
        # 提取JSON部分
        start = result.find("[")
        end = result.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        questions = json.loads(result[start:end])
        return questions if isinstance(questions, list) else []
    except Exception as e:
        print(f"  LLM解析失败: {e}")
        return []


def make_question_id(q: dict, source_url: str) -> str:
    key = q.get("definition_text", "") + q.get("question_stem", "")
    h = hashlib.md5(key.encode()).hexdigest()[:8]
    return f"true_{h}"


def deduplicate(questions: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for q in questions:
        key = (q.get("definition_text", "")[:50], q.get("answer", ""))
        if key not in seen and len(q.get("definition_text", "")) > 10:
            seen.add(key)
            result.append(q)
    return result


def collect(urls: list[str], output_path: str, max_questions: int = 200):
    all_questions = []
    today = datetime.date.today().isoformat()

    for url in urls:
        print(f"\n抓取: {url}")
        html = fetch_page(url)
        if not html:
            continue

        page_text = extract_text_from_html(html)
        if len(page_text) < 100:
            print("  页面内容太少，跳过")
            continue

        questions = llm_extract_questions(page_text, url)
        print(f"  提取到 {len(questions)} 道题")

        for q in questions:
            q["source_url"] = url
            q["source_name"] = url.split("/")[2]
            q["retrieved_at"] = today
            q["exam_year"] = "未知"
            q["exam_type"] = "未知"
            q["paper_type"] = "未知"
            q["question_type"] = "定义判断"
            q["tags"] = []
            q["id"] = make_question_id(q, url)

        all_questions.extend(questions)
        print(f"  当前累计: {len(all_questions)} 道")

        if len(all_questions) >= max_questions:
            break
        time.sleep(1.5)  # 礼貌爬取

    all_questions = deduplicate(all_questions)
    print(f"\n去重后共 {len(all_questions)} 道题")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for q in all_questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"已保存到 {output_path}")
    return all_questions


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw/raw_questions.jsonl")
    parser.add_argument("--max", type=int, default=200)
    args = parser.parse_args()

    base = os.path.join(os.path.dirname(__file__), "..")
    output_path = os.path.join(base, args.output)

    collect(QUESTION_PAGE_URLS + SEED_URLS, output_path, max_questions=args.max)
