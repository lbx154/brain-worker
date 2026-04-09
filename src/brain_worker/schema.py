"""数据结构定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Step:
    index: int
    title: str
    instruction: str
    depends_on: list[int] = field(default_factory=list)
    acceptance: str = ""
    status: StepStatus = StepStatus.PENDING
    output: str = ""
    attempts: int = 0


@dataclass
class Plan:
    goal: str
    context: str
    steps: list[Step]


@dataclass
class Review:
    passed: bool
    score: int
    feedback: str
    correction: str
