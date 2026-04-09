#!/usr/bin/env python3
"""
Brain-Worker CLI — 命令行入口

用法:
    # 默认配置 (本地 proxy)
    python -m brain_worker "写一个快速排序"

    # 自定义模型
    python -m brain_worker --planner claude-opus-4.6 --executor gpt-5-mini "任务"

    # 关闭审查 (更快)
    python -m brain_worker --no-review "简单任务"

    # 交互模式
    python -m brain_worker -i
"""

import argparse
import os
import sys

from brain_worker.models import AnthropicModel, ResponsesModel
from brain_worker.pipeline import Orchestrator


def c(text: str, color: str) -> str:
    codes = {"gray": "90", "green": "32", "cyan": "36", "bold": "1", "yellow": "33"}
    return f"\033[{codes.get(color, '0')}m{text}\033[0m"


def main():
    parser = argparse.ArgumentParser(
        description="Brain-Worker: 大模型规划+审查，小模型执行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  python -m brain_worker "写一个 LRU Cache"
  python -m brain_worker --no-review "简单任务"
  python -m brain_worker --planner claude-sonnet-4.6 --executor gpt-4o-mini "任务"
  python -m brain_worker -i
""")
    parser.add_argument("task", nargs="?", help="任务描述")
    parser.add_argument("-i", "--interactive", action="store_true", help="交互模式")
    parser.add_argument("--base-url", default=os.environ.get("BRAIN_WORKER_BASE_URL", "http://127.0.0.1:18080"), help="API base URL")
    parser.add_argument("--planner", default="claude-opus-4.6", help="规划/审查模型")
    parser.add_argument("--executor", default="gpt-5-mini", help="执行模型")
    parser.add_argument("--no-review", action="store_true", help="关闭审查 (更快)")
    parser.add_argument("--max-retries", type=int, default=2, help="每步最大重试次数")
    parser.add_argument("--max-parallel", type=int, default=3, help="最大并行数")
    args = parser.parse_args()

    planner_model = AnthropicModel(base_url=args.base_url, model=args.planner)
    executor_model = ResponsesModel(base_url=args.base_url, model=args.executor)

    orch = Orchestrator(
        planner_model=planner_model,
        executor_model=executor_model,
        review=not args.no_review,
        max_retries=args.max_retries,
        max_parallel=args.max_parallel,
    )

    if args.interactive:
        print(c("\n  Brain-Worker Framework", "bold"))
        print(c(f"  Planner: {args.planner} | Executor: {args.executor}", "gray"))
        print(c(f"  审查: {'开' if not args.no_review else '关'} | 重试: {args.max_retries} | 并行: {args.max_parallel}", "gray"))
        print(c("  输入 quit 退出\n", "gray"))

        while True:
            try:
                task = input(c(">>> ", "cyan")).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not task or task.lower() in ("quit", "exit", "q"):
                break
            result = orch.run(task)
            print(f"\n{'=' * 60}")
            print(result)
            print(f"{'=' * 60}\n")

    elif args.task:
        result = orch.run(args.task)
        print(f"\n{'=' * 60}")
        print(result)
        print(f"{'=' * 60}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
