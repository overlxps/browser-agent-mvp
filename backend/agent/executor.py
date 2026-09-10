import asyncio

from backend.schemas import Action, ActionType


class BrowserExecutor:
    """Execute a whitelisted browser action against the current Playwright page."""

    def __init__(self, page, timeout_ms: int = 8000) -> None:
        self.page = page
        self.timeout_ms = timeout_ms

    async def execute(self, action: Action) -> str:
        if action.type not in {
            ActionType.NAVIGATE,
            ActionType.CLICK,
            ActionType.FILL,
            ActionType.SELECT,
            ActionType.SCROLL,
            ActionType.EXTRACT,
            ActionType.WAIT,
            ActionType.VERIFY,
            ActionType.FINISH,
            ActionType.ASK_HUMAN,
        }:
            raise ValueError(f"动作不在白名单内：{action.type}")

        if action.type == ActionType.ASK_HUMAN:
            raise HumanAssistanceRequired(action.reason or "需要人工确认")

        match action.type:
            case ActionType.NAVIGATE:
                if not action.value:
                    raise ValueError("navigate 动作需要 value")
                await self.page.goto(action.value, wait_until="networkidle", timeout=self.timeout_ms)
                return f"已打开页面：{await self.page.title()}"
            case ActionType.CLICK:
                if not action.selector:
                    raise ValueError("click 动作需要 selector")
                await self.page.locator(action.selector).click(timeout=self.timeout_ms)
                return f"已点击 {action.selector}"
            case ActionType.FILL:
                if not action.selector or action.value is None:
                    raise ValueError("fill 动作需要 selector 和 value")
                await self.page.locator(action.selector).fill(action.value, timeout=self.timeout_ms)
                return f"已在 {action.selector} 填入 {action.value}"
            case ActionType.SELECT:
                if not action.selector or action.value is None:
                    raise ValueError("select 动作需要 selector 和 value")
                await self.page.locator(action.selector).select_option(action.value, timeout=self.timeout_ms)
                await self.page.wait_for_timeout(100)
                return f"已在 {action.selector} 选择 {action.value}"
            case ActionType.SCROLL:
                amount = int(action.value or "600")
                await self.page.mouse.wheel(0, amount)
                return f"已向下滚动 {amount}px"
            case ActionType.WAIT:
                delay_ms = int(action.value or "300")
                await self.page.wait_for_timeout(delay_ms)
                return f"已等待 {delay_ms}ms"
            case ActionType.EXTRACT:
                if not action.selector:
                    raise ValueError("extract 动作需要 selector")
                locator = self.page.locator(action.selector)
                if action.field:
                    if await locator.count() == 0:
                        raise ValueError(f"未找到选择器 {action.selector}")
                    return await locator.first.get_attribute(action.field) or await locator.first.inner_text()
                texts = [text.strip() for text in await locator.all_inner_texts()]
                return "\n".join(text for text in texts if text)
            case ActionType.VERIFY:
                if not action.selector:
                    raise ValueError("verify 动作需要 selector")
                locator = self.page.locator(action.selector)
                actual = await locator.count()
                if action.expected is not None and isinstance(action.expected, (int, float)):
                    if actual != int(action.expected):
                        raise ValueError(f"验证失败：期望 {action.expected}，实际 {actual}")
                    return f"验证通过：{action.selector} 数量为 {actual}"
                if action.field:
                    value = await locator.first.get_attribute(action.field)
                    if action.expected is not None and str(value) != str(action.expected):
                        raise ValueError(f"验证失败：期望 {action.expected}，实际 {value}")
                    return f"验证通过：{action.field}={value}"
                enabled = not await locator.first.is_disabled()
                if action.expected is not None and enabled != bool(action.expected):
                    raise ValueError(f"验证失败：期望 enabled={action.expected}，实际 {enabled}")
                return f"验证通过：{action.selector}"
            case ActionType.FINISH:
                return action.reason or "任务完成"
            case _:
                raise ValueError(f"不支持的动作：{action.type}")

    async def execute_with_retry(self, action: Action, retries: int = 1) -> tuple[str, int]:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                result = await asyncio.wait_for(self.execute(action), timeout=self.timeout_ms / 1000)
                return result, attempt
            except Exception as error:
                last_error = error
                if attempt < retries:
                    try:
                        await self.page.wait_for_timeout(200)
                    except Exception:
                        break
        raise last_error or RuntimeError("动作执行失败")


class HumanAssistanceRequired(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
