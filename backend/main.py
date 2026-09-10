import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.agent import DeterministicShoppingAgent, OpenAICompatiblePlanner
from backend.eval import build_eval_runner
from backend.schemas import LLMSettings, RunRequest, RunResult

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
SCREENSHOTS = ROOT / "runtime" / "screenshots"
STORE_URL = "http://127.0.0.1:8000/demo-store.html"
TASKFLOW_URL = "http://127.0.0.1:8000/demo-taskflow.html"
TRAVELFLOW_URL = "http://127.0.0.1:8000/demo-travelflow.html"

app = FastAPI(title="Browser Agent MVP", version="0.3.0")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
llm_settings = LLMSettings()


def build_agent() -> DeterministicShoppingAgent:
    return DeterministicShoppingAgent(STORE_URL, SCREENSHOTS, OpenAICompatiblePlanner(llm_settings))


def build_evals():
    return build_eval_runner(ROOT, llm_settings)


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(FRONTEND / "index.html")


@app.get("/demo-store.html", include_in_schema=False)
async def demo_store():
    return FileResponse(FRONTEND / "demo-store.html")


@app.get("/demo-taskflow.html", include_in_schema=False)
async def demo_taskflow():
    return FileResponse(FRONTEND / "demo-taskflow.html")


@app.get("/demo-travelflow.html", include_in_schema=False)
async def demo_travelflow():
    return FileResponse(FRONTEND / "demo-travelflow.html")


@app.get("/eval-dashboard", include_in_schema=False)
@app.get("/eval", include_in_schema=False)
async def eval_dashboard():
    return FileResponse(FRONTEND / "eval-dashboard" / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "planner": "openai-compatible" if llm_settings.api_key else "safe-fallback"}


@app.get("/api/config")
async def get_config():
    return {"base_url": llm_settings.base_url, "model": llm_settings.model, "configured": bool(llm_settings.api_key)}


@app.put("/api/config")
async def set_config(settings: LLMSettings):
    global llm_settings
    llm_settings = settings
    return {"configured": bool(llm_settings.api_key), "message": "模型配置仅保存在当前服务进程内。"}


@app.get("/api/evals/tasks")
async def list_eval_tasks():
    return build_evals().list_tasks()


@app.get("/api/evals/reports")
async def list_eval_reports():
    return build_evals().list_reports()


@app.get("/api/evals/reports/{report_id}")
async def get_eval_report(report_id: str):
    try:
        return build_evals().load_report(report_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/evals/run")
async def run_eval_suite():
    try:
        return await build_evals().run_all()
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {type(error).__name__}: {error}") from error


@app.post("/run", response_model=RunResult)
async def run_agent(request: RunRequest):
    try:
        return await build_agent().run(request)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {type(error).__name__}: {error}") from error


@app.post("/run/stream")
async def stream_agent(request: RunRequest):
    async def events():
        yield "event: status\ndata: " + json.dumps({"message": "Agent 正在启动浏览器…"}, ensure_ascii=False) + "\n\n"
        try:
            result = await build_agent().run(request)
        except Exception as error:
            payload = {"message": f"Agent 启动失败：{type(error).__name__}: {error}"}
            yield "event: error\ndata: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
            return
        for step in result.steps:
            yield "event: step\ndata: " + step.model_dump_json() + "\n\n"
            await asyncio.sleep(0.15)
        yield "event: complete\ndata: " + result.model_dump_json() + "\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
