"""
Full orchestration pipeline: big model plans and reviews, small model executes.
"""

from brain_worker import Orchestrator, AnthropicModel, ResponsesModel

BASE_URL = "http://127.0.0.1:18080"

orch = Orchestrator(
    planner_model=AnthropicModel(base_url=BASE_URL, model="claude-opus-4.6"),
    executor_model=ResponsesModel(base_url=BASE_URL, model="gpt-5-mini"),
    review=True,
    max_retries=1,
    max_parallel=2,
)

result = orch.run("Write a Python LRU Cache class with O(1) get/put and 3 test cases.")
print(result)
