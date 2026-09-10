import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import yaml

from backend.agent.verifier import evaluate_check
from backend.eval.handlers import EvalHandlers
from backend.schemas import EvalCheckResult, EvalRunReport, EvalTaskResult, LLMSettings

FAILURE_CATEGORIES = ("模型规划失败", "页面定位失败", "工具执行失败", "任务验证失败")


def classify_failure(exception: Exception | None, payload: dict, checks_passed: bool) -> str | None:
    """Map a failure to one of four categories so retries are not blind."""
    if exception is not None:
        message = str(exception)
        lowered = message.lower()
        if "planner" in lowered or "json" in lowered or "模型" in message:
            return "模型规划失败"
        if "未找到" in message or "selector" in lowered or "locator" in lowered or "timeout" in lowered or "超时" in message:
            return "页面定位失败"
        return "工具执行失败"
    if not checks_passed or not payload.get("completed", False):
        return "任务验证失败"
    return None


class EvalRunner:
    def __init__(self, tasks_dir: Path, reports_dir: Path, handlers: EvalHandlers) -> None:
        self.tasks_dir = tasks_dir
        self.reports_dir = reports_dir
        self.handlers = handlers
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def list_tasks(self) -> list[dict]:
        tasks = []
        for path in sorted(self.tasks_dir.glob("*.yaml")):
            with path.open("r", encoding="utf-8") as handle:
                tasks.append(yaml.safe_load(handle))
        return tasks

    def load_task(self, task_id: str) -> dict:
        path = self.tasks_dir / f"{task_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"未找到任务：{task_id}")
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    async def run_task(self, task: dict) -> EvalTaskResult:
        started_at = perf_counter()
        failure_reason = None
        caught: Exception | None = None
        try:
            payload = await self.handlers.run_handler(task["handler"], task.get("params", {}))
        except Exception as error:
            caught = error
            payload = {"completed": False, "failure_reasons": [str(error)], "step_count": 0, "retry_count": 0, "model_calls": 0}
            failure_reason = str(error)

        checks: list[EvalCheckResult] = []
        for check in task.get("checks", []):
            passed, detail = evaluate_check(check, payload)
            checks.append(EvalCheckResult(name=check["name"], passed=passed, detail=detail))

        duration_ms = round((perf_counter() - started_at) * 1000)
        passed = all(check.passed for check in checks) and payload.get("completed", False)
        reasons = payload.get("failure_reasons", [])
        if not passed and not failure_reason and reasons:
            failure_reason = reasons[0]
        failure_category = None if passed else classify_failure(caught, payload, all(check.passed for check in checks))

        return EvalTaskResult(
            task_id=task["id"],
            site=task["site"],
            description=task.get("description", ""),
            instruction=task.get("instruction", task.get("description", "")),
            passed=passed,
            duration_ms=duration_ms,
            step_count=payload.get("step_count", 0),
            retry_count=payload.get("retry_count", 0),
            model_calls=payload.get("model_calls", 0),
            failure_reason=failure_reason,
            failure_category=failure_category,
            screenshot_path=payload.get("screenshot_path"),
            checks=checks,
            metadata={"handler": task["handler"], "expected": task.get("expected", {})},
        )

    async def run_all(self, task_ids: list[str] | None = None) -> EvalRunReport:
        started_at = perf_counter()
        tasks = [self.load_task(task_id) for task_id in task_ids] if task_ids else self.list_tasks()
        results = [await self.run_task(task) for task in tasks]
        total = len(results)
        passed_count = sum(1 for result in results if result.passed)
        failure_reasons = [result.failure_reason for result in results if result.failure_reason]
        failure_categories: dict[str, int] = {}
        for result in results:
            if result.failure_category:
                failure_categories[result.failure_category] = failure_categories.get(result.failure_category, 0) + 1
        report = EvalRunReport(
            report_id=uuid4().hex[:12],
            created_at=datetime.now(timezone.utc).isoformat(),
            passed=passed_count == total,
            total=total,
            passed_count=passed_count,
            failed_count=total - passed_count,
            duration_ms=round((perf_counter() - started_at) * 1000),
            success_rate=round((passed_count / total) * 100, 1) if total else 0.0,
            average_duration_ms=round(sum(result.duration_ms for result in results) / total, 1) if total else 0.0,
            average_steps=round(sum(result.step_count for result in results) / total, 1) if total else 0.0,
            average_retries=round(sum(result.retry_count for result in results) / total, 1) if total else 0.0,
            failure_reasons=failure_reasons,
            failure_categories=failure_categories,
            results=results,
        )
        report_path = self.reports_dir / f"{report.report_id}.json"
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return report

    def list_reports(self) -> list[dict]:
        reports = []
        for path in sorted(self.reports_dir.glob("*.json"), reverse=True):
            data = json.loads(path.read_text(encoding="utf-8"))
            reports.append(
                {
                    "report_id": data["report_id"],
                    "created_at": data["created_at"],
                    "passed": data["passed"],
                    "total": data["total"],
                    "passed_count": data["passed_count"],
                    "failed_count": data["failed_count"],
                    "duration_ms": data["duration_ms"],
                    "success_rate": data.get("success_rate", 0),
                    "average_duration_ms": data.get("average_duration_ms", 0),
                    "average_steps": data.get("average_steps", 0),
                }
            )
        return reports

    def load_report(self, report_id: str) -> EvalRunReport:
        path = self.reports_dir / f"{report_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"未找到报告：{report_id}")
        return EvalRunReport.model_validate_json(path.read_text(encoding="utf-8"))


def build_eval_runner(root: Path, llm_settings: LLMSettings) -> EvalRunner:
    handlers = EvalHandlers(
        shopflow_url="http://127.0.0.1:8000/demo-store.html",
        taskflow_url="http://127.0.0.1:8000/demo-taskflow.html",
        travelflow_url="http://127.0.0.1:8000/demo-travelflow.html",
        screenshot_dir=root / "runtime" / "screenshots",
        llm_settings=llm_settings,
    )
    return EvalRunner(root / "tasks", root / "reports", handlers)
