# Browser Agent MVP

一个面试展示用途的浏览器 Agent 平台原型：用户输入商品检索条件，后端用 Playwright 操作 `ShopFlow` 本地任务环境，完成搜索、筛选、分页提取与结果验证，并返回可追溯的执行轨迹。

## 设计边界

- 仅允许访问本地 `ShopFlow` 任务环境；它包含搜索、筛选、排序、分页和详情状态，避免真实站点、登录、支付和验证码风险。
- 浏览器执行与“规划”分离：未配模型时使用确定性回退；配置 OpenAI 兼容接口后，LLM 会根据页面观察在白名单动作中选择下一步。
- 每次执行都会返回步骤日志；搜索后还会保存截图到 `runtime/screenshots/`。

## 快速启动

```powershell
cd browser-agent-mvp
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
uvicorn backend.main:app
```

访问 http://127.0.0.1:8000 ，输入“无线耳机”、价格 `500`、评分 `4.5`，点击开始执行。

> Windows 上运行 Playwright 时不要添加 `--reload`：热重载会使用与 Chromium 启动不兼容的事件循环。修改代码后请停止服务并重新运行上述命令。

如需启用模型，在页面展开“模型设置”，填写 OpenAI 兼容接口的 Base URL、模型名和 API Key。密钥仅保存在当前服务进程内，重启后需要重新填写；模型不可用或输出不符合动作规则时会自动回退。

## API

`POST /run` 接收：

```json
{"query":"无线耳机","max_price":500,"min_rating":4.5,"limit":3}
```

`POST /run/stream` 以 SSE 返回 `status`、`step` 与 `complete` 事件，供前端实时展示。

`POST /api/evals/shopflow` 运行第一个固定评测任务：在无线耳机中找出 3 个价格不超过 ¥500、评分不低于 4.5 的结果，并返回通过状态、耗时、步骤数和每项断言的结果。

## 面试可讲的点

1. **混合架构**：规划逻辑与确定性浏览器动作解耦，避免让模型直接操作不受控的环境。
2. **可观测性**：每一步都有动作、观察和截图证据。
3. **安全边界**：来源白名单、无登录/支付、最大步骤数为后续 LLM 循环预留。
4. **循环保护**：最大 6 步、重复搜索保护、完成前必须取得结构化数据，避免模型死循环或跳过验证。
5. **演进路径**：加入滚动、筛选控件和多站点任务评测集，再逐步扩大白名单工具。

## 测试

```powershell
pytest
```
