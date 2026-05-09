from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrueQuestion:
    id: str
    source_url: str
    source_name: str
    retrieved_at: str
    exam_year: str
    exam_type: str
    paper_type: str
    question_type: str = "定义判断"
    ask_type: str = ""
    definition_text: str = ""
    question_stem: str = ""
    options: dict = field(default_factory=dict)
    answer: str = ""
    explanation: str = ""
    tags: list = field(default_factory=list)
    split: str = "train"
    source_quality: str = "ok"
    answer_confidence: str = "ok"


@dataclass
class GeneratedQuestion:
    id: str
    epoch: int
    question_type: str = "定义判断"
    ask_type: str = ""
    definition_text: str = ""
    question_stem: str = ""
    options: dict = field(default_factory=dict)
    answer: str = ""
    explanation: str = ""
    generation_notes: dict = field(default_factory=dict)
    self_check_result: str = ""
    blind_solve_answer: str = ""
    answer_consistent: Optional[bool] = None


@dataclass
class PairwiseResult:
    epoch: int
    generated_id: str
    true_id: str
    winner: str        # "generated" / "true" / "tie"
    reason: str
    scores: dict = field(default_factory=dict)
