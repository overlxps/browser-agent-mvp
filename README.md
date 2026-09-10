# Browser Agent MVP

一个面试展示用途的浏览器 Agent 平台原型：包含 ShopFlow、TaskFlow、TravelFlow 三个本地任务环境，以及可追踪的状态机执行与 10 项固定评测。

## 三个本地任务环境

| 环境 | 能力 |
|------|------|
| ShopFlow | 商品检索、筛选、排序、分页、详情 |
| TaskFlow | 看板筛选、状态修改、优先级排序 |
| TravelFlow | 表单填写、多条件筛选、比较与推荐 |

## Agent 状态机

```
Observe → Planner 选择动作 → Executor 执行 → Verify 验证 → Memory 记录 → 完成 / 重试 / ask_human
```

白名单动作：`navigate` `click` `fill` `select` `scroll` `extract` `wait` `verify` `finish` `ask_human`

## 快速启动

```powershell
cd browser-agent-mvp
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
uvicorn backend.main:app
```

访问：

- 任务执行：http://127.0.0.1:8000
- ShopFlow：http://127.0.0.1:8000/demo-store.html
- TaskFlow：http://127.0.0.1:8000/demo-taskflow.html
- TravelFlow：http://127.0.0.1:8000/demo-travelflow.html
- 评测面板：http://127.0.0.1:8000/eval

## 评测任务（10 项）

运行全部评测：

```powershell
curl -X POST http://127.0.0.1:8000/api/evals/run
```

结果写入 `reports/`，面板展示成功率、平均耗时、平均步骤、失败原因。

## 失败分类（四分类）

评测把每次失败归入四类，不同类别对应不同处理策略，而不是统一重试：

| 类别 | 含义 | 处理策略 |
|------|------|----------|
| 模型规划失败 | 规划器输出非法或模型不可用 | 回退到确定性动作序列 |
| 页面定位失败 | 选择器未命中、超时 | 重试一次，仍失败则熔断 |
| 工具执行失败 | 浏览器或运行时异常 | 记录原因并停止该任务 |
| 任务验证失败 | 断言不通过或结果不完整 | 保留证据供复盘 |

评测面板 `/eval` 会展示每类失败的任务数量与逐任务明细。

## 可靠性与安全

- 最大步数限制（`max_steps`）与连续失败熔断（`max_consecutive_failures`）
- 动作白名单：执行器只接受枚举内的动作类型
- 每个动作执行后回读页面状态验证（`verify`），而非假设成功
- 工具超时（`asyncio.wait_for`）与自动重试（`execute_with_retry`）
- 模型输出 JSON 校验，非法动作不会到达浏览器
- `ask_human`：登录、验证码、支付、歧义选项时暂停请求人工
- 截图按运行 ID 隔离，不同任务的证据链不会互相覆盖

## 数据稳定性

演示站点的日期基于运行当天动态生成：

- TaskFlow 任务截止日期为相对今天的偏移，逾期任务数量恒定
- TravelFlow 月份选项为当前月与下月，任务定义用 `current` 指代

这保证评测任务不会因日历翻页而失效。

## 测试

```powershell
pytest
```
