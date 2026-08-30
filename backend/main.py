import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.agent import DeterministicShoppingAgent, OpenAICompatiblePlanner
from backend.eval.shopflow import evaluate_shopflow
from backend.schemas import LLMSettings, RunRequest, RunResult

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
SCREENSHOTS = ROOT / "runtime" / "screenshots"
STORE_URL = "http://127.0.0.1:8000/demo-store.html"

app = FastAPI(title="Browser Agent MVP", version="0.1.0")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
llm_settings = LLMSettings()


def build_agent() -> DeterministicShoppingAgent:
    return DeterministicShoppingAgent(STORE_URL, SCREENSHOTS, OpenAICompatiblePlanner(llm_settings))


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(FRONTEND / "index.html")


@app.get("/demo-store.html", include_in_schema=False)
async def demo_store():
    return FileResponse(FRONTEND / "demo-store.html")


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


@app.post("/api/evals/shopflow")
async def run_shopflow_evaluation():
    try:
        return await evaluate_shopflow(build_agent())
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
