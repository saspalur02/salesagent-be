"""
AI Agent Core menggunakan LiteLLM.
2 mode: TOKO (susun draft order) dan ADMIN (finalisasi → buat SO).
"""
import json
import os
import litellm
from app.core.settings import get_settings
from app.core.logging import get_logger
from app.services.ai.tools import TOKO_TOOLS, ADMIN_TOOLS
from app.services.ai.executor import TokoToolExecutor, AdminToolExecutor
from app.services.ai.prompt import TOKO_AGENT_PROMPT, ADMIN_AGENT_PROMPT
from app.services.erp import ERPClient

settings = get_settings()
logger = get_logger(__name__)

if settings.litellm_api_key:
    os.environ["OPENAI_API_KEY"] = settings.litellm_api_key


class SalesAgent:
    MAX_TOOL_ROUNDS = 6

    def __init__(self, erp_client: ERPClient):
        self.erp = erp_client
        self.model = settings.litellm_model
        self.max_tokens = settings.litellm_max_tokens
        self.temperature = settings.litellm_temperature

    async def process_toko(
        self,
        message: str,
        wa_number: str,
        history: list[dict],
    ) -> str:
        """Proses pesan dari toko — susun draft order."""
        executor = TokoToolExecutor(self.erp, wa_number)
        messages = [{"role": "system", "content": TOKO_AGENT_PROMPT}]
        messages.extend(history[-20:])
        messages.append({"role": "user", "content": message})
        return await self._run(messages, TOKO_TOOLS, executor)

    async def process_admin(
        self,
        message: str,
        history: list[dict],
    ) -> str:
        """Proses pesan dari admin — validasi & buat SO."""
        executor = AdminToolExecutor(self.erp)
        messages = [{"role": "system", "content": ADMIN_AGENT_PROMPT}]
        messages.extend(history[-20:])
        messages.append({"role": "user", "content": message})
        return await self._run(messages, ADMIN_TOOLS, executor)

    async def _run(self, messages: list, tools: list, executor) -> str:
        """Core tool-calling loop."""
        for round_num in range(self.MAX_TOOL_ROUNDS):
            logger.info("agent_llm_call", round=round_num, model=self.model)

            kwargs = dict(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            if settings.litellm_api_base:
                kwargs["api_base"] = settings.litellm_api_base

            response = await litellm.acompletion(**kwargs)
            response_message = response.choices[0].message

            if not response_message.tool_calls:
                return response_message.content or ""

            logger.info(
                "agent_tool_calls",
                tools=[tc.function.name for tc in response_message.tool_calls],
            )

            messages.append(response_message)

            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                tool_result = await executor.execute(tool_name, tool_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })

        logger.warning("agent_max_rounds_exceeded")
        return "Maaf, terjadi kendala. Silakan coba lagi."
