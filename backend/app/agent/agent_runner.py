"""OneFL Agent Runner & Orchestration Engine.

Implements the ReAct (Reasoning + Acting) pattern and Tool Calling execution loop,
handling dynamic tool selection, parameter validation, automatic reflection on errors,
and trajectory auditing.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.agent.tools import agent_toolkit
from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class AgentStep(BaseModel):
    """Represents a single step in the ReAct execution trajectory."""
    step_index: int = Field(..., description="Thứ tự bước thực thi (1-indexed)")
    thought: str = Field(..., description="Suy luận của agent về bước đi hiện tại")
    action: Optional[str] = Field(None, description="Tên tool được chọn để gọi")
    action_input: Optional[Dict[str, Any]] = Field(None, description="Tham số truyền vào cho tool")
    observation: Optional[Any] = Field(None, description="Kết quả quan sát được từ tool")
    is_error: bool = Field(False, description="Đánh dấu bước này có gặp lỗi không")


class AgentExecutionResult(BaseModel):
    """Represents the final result of an agent run."""
    goal: str = Field(..., description="Mục tiêu ban đầu được giao cho agent")
    final_answer: str = Field(..., description="Câu trả lời hoặc kết luận cuối cùng")
    trajectory: List[AgentStep] = Field(default_factory=list, description="Toàn bộ chuỗi suy luận và hành động")
    total_steps: int = Field(0, description="Tổng số bước ReAct đã thực thi")
    success: bool = Field(True, description="Trạng thái hoàn thành thành công")


AGENT_SYSTEM_PROMPT = """Bạn là OneFL Autonomous Subtitle & Video Translation Agent - Trợ lý AI chuyên gia tối thượng về dịch thuật phụ đề phim và xử lý video đa ngôn ngữ.

Bạn có quyền truy cập vào danh sách các công cụ chuyên dụng dưới đây:
{tools_manifest}

HƯỚNG DẪN HOẠT ĐỘNG THEO CHU TRÌNH ReAct (Suy luận & Hành động):
Ở mỗi lượt, hãy phân tích mục tiêu của người dùng, xem xét lịch sử các bước đã thực hiện (nếu có), và quyết định bước tiếp theo.

Bạn BẮT BUỘC trả về định dạng thuần JSON (không bọc trong markdown dư thừa), theo một trong hai cấu trúc sau:

Cấu trúc 1 - Khi cần gọi tool:
{{
  "thought": "Giải thích chi tiết lý do bạn chọn tool này và mục đích thực hiện.",
  "action": "tên_tool_chính_xác",
  "action_input": {{ ...các tham số khớp với schema của tool... }}
}}

Cấu trúc 2 - Khi đã có đủ thông tin và hoàn thành nhiệm vụ:
{{
  "thought": "Đã có đủ dữ liệu từ các bước quan sát trước đó để trả lời người dùng.",
  "final_answer": "Nội dung trả lời chi tiết, chuyên nghiệp, chính xác cho người dùng."
}}

LƯU Ý CỐT LÕI:
1. Chỉ chọn các tool có trong danh sách được cung cấp.
2. Nếu quan sát trước đó báo lỗi (Observation chứa error), hãy tự phản tỉnh (Reflection), sửa lại tham số hoặc đổi công cụ phù hợp.
3. Luôn đảm bảo tên tham số khớp 100% với schema đã cung cấp.
"""


class OneFLAgentRunner:
    """Orchestrates multi-turn ReAct reasoning and dynamic tool execution."""

    def __init__(self, llm_router: Optional[LLMRouter] = None):
        self.llm_router = llm_router or LLMRouter()
        self.toolkit = agent_toolkit

    def _build_tools_manifest(self) -> str:
        """Builds a formatted catalog of all available tools and their parameter schemas."""
        manifest_lines = []
        for tool in self.toolkit.list_tools():
            schema = tool.to_function_calling_schema()
            fn = schema.get("function", {})
            name = fn.get("name", tool.name)
            desc = fn.get("description", tool.description)
            params = json.dumps(fn.get("parameters", {}), ensure_ascii=False, indent=2)
            manifest_lines.append(f"- Tool: `{name}`\n  Mô tả: {desc}\n  Schema tham số:\n{params}\n")
        return "\n".join(manifest_lines)

    async def execute_tool_direct(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Directly invokes a tool by name with arguments without LLM reasoning loop."""
        return await self.toolkit.execute(tool_name, arguments)

    def _clean_json_text(self, text: str) -> str:
        """Removes markdown code block wrappings and extracts clean JSON object."""
        cleaned = text.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if match:
            return match.group(1).strip()
        if cleaned.startswith("{") and cleaned.endswith("}"):
            return cleaned
        # Try finding first { and last }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return cleaned[start : end + 1].strip()
        return cleaned

    async def run(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        max_iterations: int = 5
    ) -> AgentExecutionResult:
        """Executes the autonomous ReAct reasoning and tool calling loop.

        Args:
            goal: The target prompt or mission given by the user.
            context: Additional metadata or context variables (e.g. video_path, project_id).
            max_iterations: Maximum ReAct steps before forcing a conclusion.

        Returns:
            AgentExecutionResult containing the full trajectory and final answer.
        """
        trajectory: List[AgentStep] = []
        tools_manifest = self._build_tools_manifest()
        system_prompt = AGENT_SYSTEM_PROMPT.format(tools_manifest=tools_manifest)

        history_log: List[str] = [
            f"MỤC TIÊU CỦA NGƯỜI DÙNG: {goal}",
        ]
        if context:
            history_log.append(f"NGỮ CẢNH BỔ SUNG: {json.dumps(context, ensure_ascii=False)}")

        for iteration in range(1, max_iterations + 1):
            user_prompt = "\n\n".join(history_log) + f"\n\nBƯỚC HIỆN TẠI: Bước {iteration}/{max_iterations}. Hãy suy luận và đưa ra quyết định dạng JSON."

            try:
                raw_response = await self.llm_router.generate_completion(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.2
                )
            except Exception as llm_err:
                logger.warning(f"LLM call failed during Agent ReAct step {iteration}: {llm_err}")
                # Handle gracefully when LLM API keys are missing or offline
                err_step = AgentStep(
                    step_index=iteration,
                    thought=f"Không thể kết nối LLM service: {llm_err}. Kích hoạt chế độ cứu cánh.",
                    action=None,
                    action_input=None,
                    observation=str(llm_err),
                    is_error=True
                )
                trajectory.append(err_step)
                return AgentExecutionResult(
                    goal=goal,
                    final_answer=f"Lỗi kết nối LLM: {llm_err}. Vui lòng cấu hình GEMINI_API_KEY hoặc OPENAI_API_KEY để kích hoạt tính năng Agent tự trị.",
                    trajectory=trajectory,
                    total_steps=iteration,
                    success=False
                )

            cleaned_json = self._clean_json_text(raw_response)
            try:
                parsed = json.loads(cleaned_json)
            except Exception as parse_err:
                logger.warning(f"JSON parsing error from LLM response: {parse_err}. Response was: {raw_response[:200]}")
                step = AgentStep(
                    step_index=iteration,
                    thought="Phản hồi từ LLM không đúng định dạng JSON chuẩn. Yêu cầu LLM thử lại.",
                    action=None,
                    action_input=None,
                    observation=f"JSON parse error: {parse_err}. Raw text: {raw_response[:200]}",
                    is_error=True
                )
                trajectory.append(step)
                history_log.append(f"Observation (Bước {iteration}): Phản hồi không phải JSON hợp lệ. Vui lòng CHỈ trả về đúng JSON theo hướng dẫn.")
                continue

            thought = parsed.get("thought", "Không có suy luận cụ thể.")
            final_answer = parsed.get("final_answer")

            # Check if Agent provided a final answer
            if final_answer:
                step = AgentStep(
                    step_index=iteration,
                    thought=thought,
                    action=None,
                    action_input=None,
                    observation="Nhiệm vụ hoàn thành.",
                    is_error=False
                )
                trajectory.append(step)
                return AgentExecutionResult(
                    goal=goal,
                    final_answer=final_answer,
                    trajectory=trajectory,
                    total_steps=iteration,
                    success=True
                )

            # Otherwise, an action is expected
            action = parsed.get("action")
            action_input = parsed.get("action_input", {})

            if not action:
                step = AgentStep(
                    step_index=iteration,
                    thought=thought,
                    action=None,
                    action_input=None,
                    observation="LLM không chỉ định action hoặc final_answer hợp lệ.",
                    is_error=True
                )
                trajectory.append(step)
                history_log.append(f"Observation (Bước {iteration}): Thiếu trường 'action' hoặc 'final_answer' trong JSON.")
                continue

            # Execute tool with automatic error capturing & reflection
            try:
                tool_result = await self.toolkit.execute(action, action_input)
                obs_summary = json.dumps(tool_result, ensure_ascii=False)
                step = AgentStep(
                    step_index=iteration,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=tool_result,
                    is_error=False
                )
                trajectory.append(step)
                history_log.append(f"Action (Bước {iteration}): {action}({json.dumps(action_input, ensure_ascii=False)})\nObservation: {obs_summary}")
            except Exception as exec_err:
                logger.error(f"Error executing tool '{action}': {exec_err}")
                step = AgentStep(
                    step_index=iteration,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=f"ERROR: {str(exec_err)}",
                    is_error=True
                )
                trajectory.append(step)
                history_log.append(
                    f"Action (Bước {iteration}): {action}\n"
                    f"Observation (ERROR): Thực thi công cụ thất bại: {exec_err}. "
                    f"Hãy tự phản tỉnh (Reflection), kiểm tra lại kiểu dữ liệu và tham số của công cụ, sau đó thử lại."
                )

        # If loop ended without explicit final_answer
        return AgentExecutionResult(
            goal=goal,
            final_answer="Đã đạt giới hạn số bước ReAct (max_iterations) mà chưa thể hoàn thành toàn bộ mục tiêu.",
            trajectory=trajectory,
            total_steps=max_iterations,
            success=False
        )


agent_runner = OneFLAgentRunner()
