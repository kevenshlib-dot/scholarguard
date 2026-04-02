"""
LLM统一客户端
通过LiteLLM实现本地/远程模型的统一调用与智能路由
"""

import logging
import time
from typing import Optional

import litellm

logger = logging.getLogger(__name__)

# 禁用 litellm 的默认日志
litellm.set_verbose = False


# 默认模型路由表
# 模型名格式:
#   - "openai/<model>" : 通过vLLM的OpenAI兼容接口调用本地模型
#   - "ollama/<model>" : 通过Ollama调用
#   - "gpt-4o" 等     : 直接调用远程API
DEFAULT_MODEL_ROUTES = {
    "detection": {
        "primary": "openai//home/dell/models/Qwen3.5-27B",
        "fallback": "gpt-4o",
        "degradation": "ollama/qwen2.5:7b",
    },
    "suggestion": {
        "primary": "openai//home/dell/models/Qwen3.5-27B",
        "fallback": "claude-sonnet-4-20250514",
        "degradation": "ollama/qwen2.5:7b",
    },
    "translation": {
        "primary": "openai//home/dell/models/Qwen3.5-27B",
        "fallback": "gpt-4o",
        "degradation": None,
    },
    "ocr": {
        "primary": "gemini/gemini-2.5-pro",
        "fallback": "gpt-4o",
        "degradation": None,
    },
}


class LLMClient:
    """
    统一LLM调用客户端

    特性：
    - 通过LiteLLM统一本地(Ollama/vLLM)和远程(OpenAI/Anthropic/Google)模型
    - 任务级模型路由
    - 自动降级（primary → fallback → degradation）
    - 成本跟踪
    - 响应时间监控
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        vllm_url: str = "http://192.168.31.18:8001/v1",
        model_routes: Optional[dict] = None,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
    ):
        self.ollama_url = ollama_url
        self.vllm_url = vllm_url
        self.model_routes = model_routes or DEFAULT_MODEL_ROUTES
        self._usage_log: list[dict] = []
        self._last_used_model: dict[str, str] = {}  # task_type → 实际使用的模型

        # 保存 API keys（在调用时按模型类型传入，而非设置 litellm 全局变量）
        self._api_keys = {
            "openai": openai_api_key,
            "anthropic": anthropic_api_key,
            "google": google_api_key,
        }

    def get_current_model(self, task_type: str) -> str:
        """获取任务实际使用的模型（优先返回最近一次调用使用的模型）"""
        if task_type in self._last_used_model:
            return self._last_used_model[task_type]
        route = self.model_routes.get(task_type, {})
        return route.get("primary", "ollama/qwen2.5:7b")

    async def chat(
        self,
        task_type: str,
        system_prompt: str,
        user_prompt: str,
        model_override: Optional[str] = None,
        response_format: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """
        统一的LLM对话接口

        Args:
            task_type: 任务类型（用于路由选择）
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            model_override: 指定模型（跳过路由）
            response_format: 响应格式 ("json" 或 None)
            max_tokens: 最大输出token数
            temperature: 温度参数

        Returns:
            模型响应文本
        """
        route = self.model_routes.get(task_type, {})
        models_to_try = []

        if model_override:
            models_to_try = [model_override]
        else:
            for key in ["primary", "fallback", "degradation"]:
                model = route.get(key)
                if model:
                    models_to_try.append(model)

        if not models_to_try:
            models_to_try = ["ollama/qwen2.5:7b"]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error = None
        for model in models_to_try:
            try:
                start_time = time.time()

                kwargs = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }

                # 模型路由：按类型设置 api_base 和 api_key
                if model.startswith("ollama/"):
                    kwargs["api_base"] = self.ollama_url
                elif model.startswith("openai/") and self.vllm_url:
                    # vLLM的OpenAI兼容接口
                    kwargs["api_base"] = self.vllm_url
                    kwargs["api_key"] = "not-needed"  # vLLM不需要API key
                    # Qwen3.5: 禁用thinking mode以获取结构化JSON输出
                    kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
                    # vLLM性能优化参数
                    kwargs["top_p"] = 0.9              # 略微缩小采样空间
                    kwargs["repetition_penalty"] = 1.0  # 结构化输出无需重复惩罚
                elif model.startswith("gemini/"):
                    if self._api_keys.get("google"):
                        kwargs["api_key"] = self._api_keys["google"]
                    # Gemini 2.5 思考模型：增大 max_tokens 以容纳 thinking + 实际输出
                    # thinking tokens 也计入 max_tokens，默认 2048 不够
                    kwargs["max_tokens"] = max(max_tokens, 8192)
                elif model.startswith("claude-"):
                    if self._api_keys.get("anthropic"):
                        kwargs["api_key"] = self._api_keys["anthropic"]
                elif model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3") or model.startswith("o4"):
                    if self._api_keys.get("openai"):
                        kwargs["api_key"] = self._api_keys["openai"]

                # JSON模式
                # - vLLM/openai 模型：通过 prompt 要求 JSON（不设 response_format）
                # - Gemini 思考模型：不设 json_object（可能导致空响应），通过 prompt 要求
                # - 其他远程模型（GPT、Claude）：设 json_object
                if response_format == "json":
                    if not model.startswith("openai/") and not model.startswith("gemini/"):
                        kwargs["response_format"] = {"type": "json_object"}

                response = await litellm.acompletion(**kwargs)

                elapsed_ms = int((time.time() - start_time) * 1000)
                msg = response.choices[0].message
                content = msg.content

                # 思考模型（Qwen3.5/Gemini 2.5）: content可能为None或空，
                # 实际内容在reasoning_content或其他字段中
                if not content or content.strip() == "":
                    # 尝试从 reasoning_content 获取
                    reasoning = getattr(msg, "reasoning_content", None)
                    if reasoning:
                        content = reasoning
                    # 尝试从 provider_specific_fields 获取
                    if not content and hasattr(msg, "provider_specific_fields"):
                        psf = msg.provider_specific_fields or {}
                        content = psf.get("reasoning_content") or psf.get("reasoning") or ""
                    # 尝试从 model_extra 获取（litellm 某些版本）
                    if not content and hasattr(msg, "model_extra"):
                        extra = msg.model_extra or {}
                        content = extra.get("reasoning_content") or extra.get("thinking") or ""

                if not content:
                    logger.warning(
                        f"模型 {model} 返回空内容，跳过。"
                        f"msg attrs: {[a for a in dir(msg) if not a.startswith('_')]}"
                    )
                    continue

                # 记录使用日志
                usage = response.usage
                self._log_usage(
                    task_type=task_type,
                    model=model,
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                    elapsed_ms=elapsed_ms,
                )

                # 记录实际使用的模型
                self._last_used_model[task_type] = model

                logger.info(
                    f"LLM调用成功: model={model}, task={task_type}, "
                    f"tokens={usage.total_tokens if usage else '?'}, "
                    f"耗时={elapsed_ms}ms"
                )

                return content

            except Exception as e:
                last_error = e
                logger.warning(
                    f"LLM调用失败 model={model}: {type(e).__name__}: {e}"
                )
                continue

        raise RuntimeError(
            f"所有模型调用均失败 (task={task_type}): {last_error}"
        )

    async def chat_with_image(
        self,
        task_type: str,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
        mime_type: str = "image/png",
        model_override: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """
        带图片的LLM对话接口（用于OCR等视觉任务）

        Args:
            task_type: 任务类型（用于路由选择）
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            image_base64: Base64编码的图片数据
            mime_type: 图片MIME类型
            model_override: 指定模型（跳过路由）
            max_tokens: 最大输出token数
            temperature: 温度参数

        Returns:
            模型响应文本
        """
        route = self.model_routes.get(task_type, {})
        models_to_try = []

        if model_override:
            models_to_try = [model_override]
        else:
            for key in ["primary", "fallback", "degradation"]:
                model = route.get(key)
                if model:
                    models_to_try.append(model)

        if not models_to_try:
            raise RuntimeError(f"没有为任务类型 '{task_type}' 配置可用模型")

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}",
                        },
                    },
                ],
            },
        ]

        last_error = None
        for model in models_to_try:
            try:
                start_time = time.time()

                kwargs = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }

                # 模型路由：按类型设置 api_base 和 api_key
                if model.startswith("gemini/"):
                    if self._api_keys.get("google"):
                        kwargs["api_key"] = self._api_keys["google"]
                    kwargs["max_tokens"] = max(max_tokens, 8192)
                elif model.startswith("claude-"):
                    if self._api_keys.get("anthropic"):
                        kwargs["api_key"] = self._api_keys["anthropic"]
                elif model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3") or model.startswith("o4"):
                    if self._api_keys.get("openai"):
                        kwargs["api_key"] = self._api_keys["openai"]

                response = await litellm.acompletion(**kwargs)

                elapsed_ms = int((time.time() - start_time) * 1000)
                msg = response.choices[0].message
                content = msg.content

                if not content or content.strip() == "":
                    reasoning = getattr(msg, "reasoning_content", None)
                    if reasoning:
                        content = reasoning
                    if not content and hasattr(msg, "provider_specific_fields"):
                        psf = msg.provider_specific_fields or {}
                        content = psf.get("reasoning_content") or psf.get("reasoning") or ""
                    if not content and hasattr(msg, "model_extra"):
                        extra = msg.model_extra or {}
                        content = extra.get("reasoning_content") or extra.get("thinking") or ""

                if not content:
                    logger.warning(f"视觉模型 {model} 返回空内容，跳过。")
                    continue

                usage = response.usage
                self._log_usage(
                    task_type=task_type,
                    model=model,
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                    elapsed_ms=elapsed_ms,
                )
                self._last_used_model[task_type] = model

                logger.info(
                    f"视觉LLM调用成功: model={model}, task={task_type}, "
                    f"tokens={usage.total_tokens if usage else '?'}, "
                    f"耗时={elapsed_ms}ms"
                )

                return content

            except Exception as e:
                last_error = e
                logger.warning(
                    f"视觉LLM调用失败 model={model}: {type(e).__name__}: {e}"
                )
                continue

        raise RuntimeError(
            f"所有视觉模型调用均失败 (task={task_type}): {last_error}"
        )

    def _log_usage(self, task_type: str, model: str,
                   input_tokens: int, output_tokens: int,
                   elapsed_ms: int):
        """记录使用日志"""
        cost = self._estimate_cost(model, input_tokens, output_tokens)
        entry = {
            "task_type": task_type,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "elapsed_ms": elapsed_ms,
            "timestamp": time.time(),
        }
        self._usage_log.append(entry)
        # 只保留最近1000条
        if len(self._usage_log) > 1000:
            self._usage_log = self._usage_log[-500:]

    def _estimate_cost(self, model: str, input_tokens: int,
                       output_tokens: int) -> float:
        """估算调用成本（USD）"""
        # 本地模型：仅电力成本折算
        if model.startswith("ollama/") or model.startswith("vllm/"):
            return (input_tokens + output_tokens) * 0.000001

        # 远程模型成本表（USD per 1K tokens）
        cost_table = {
            "gpt-4o": (0.005, 0.015),
            "gpt-4o-mini": (0.00015, 0.0006),
            "claude-sonnet-4-20250514": (0.003, 0.015),
            "claude-opus-4-20250514": (0.015, 0.075),
            "gemini/gemini-2.5-pro": (0.00125, 0.005),
        }

        rates = cost_table.get(model, (0.001, 0.003))
        return (input_tokens * rates[0] + output_tokens * rates[1]) / 1000

    def get_usage_summary(self) -> dict:
        """获取使用量摘要"""
        total_cost = sum(e["cost_usd"] for e in self._usage_log)
        total_tokens = sum(
            e["input_tokens"] + e["output_tokens"] for e in self._usage_log
        )
        model_breakdown = {}
        for e in self._usage_log:
            model = e["model"]
            if model not in model_breakdown:
                model_breakdown[model] = {"calls": 0, "cost": 0.0, "tokens": 0}
            model_breakdown[model]["calls"] += 1
            model_breakdown[model]["cost"] += e["cost_usd"]
            model_breakdown[model]["tokens"] += e["input_tokens"] + e["output_tokens"]

        return {
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "total_calls": len(self._usage_log),
            "model_breakdown": model_breakdown,
        }
