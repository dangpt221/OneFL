"""OneFL Agent Runner & Orchestration Engine.

Implements the ReAct (Reasoning + Acting) pattern and Tool Calling execution loop,
handling dynamic tool selection, parameter validation, automatic reflection on errors,
and trajectory auditing.
"""

import asyncio
import time
import json
import logging
import re
from typing import Literal, Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.agent.tools import agent_toolkit
from app.agent.contracts import AgentDecision, bounded_observation
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
    state: Literal['COMPLETED', 'PENDING', 'FAILED'] = 'COMPLETED'
    jobs: List[Dict[str, Any]] = Field(default_factory=list)
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
        if not goal.strip() or len(goal) > 4000 or not 1 <= max_iterations <= 10:
            raise ValueError('Use a nonempty goal up to 4000 characters and 1–10 iterations')
        context = dict(context or {})
        if len(json.dumps(context, allow_nan=False)) > 8000:
            raise ValueError('Context exceeds 8000 characters; pass project IDs instead of transcripts')
        from app.services.agent_project_service import owned_project, get_async_session, job_status, verify_artifact
        project_id = context.get('project_id')
        expected = context.get('expected_artifact')
        if expected and (not project_id or expected not in {'burned_video', 'dubbed_video', 'subtitles', 'transcript', 'translated_cues'}):
            raise ValueError('expected_artifact requires project_id and a supported artifact kind')
        if project_id:
            async with get_async_session() as db:
                await owned_project(db, project_id)
        trajectory: List[AgentStep] = []
        jobs: list[dict[str, Any]] = []
        unresolved_error = False
        system_prompt = AGENT_SYSTEM_PROMPT.format(tools_manifest=self._build_tools_manifest())
        system_prompt += ('\nMedia tools return QUEUED jobs, not completed artifacts. Use wait_for_job/get_job_status. '
                          'Never claim media completion before a successful job and a current persisted artifact. '
                          'Use project IDs/paginated context, not full transcripts. Set subtitle preset during export, not burn.')
        prefix = f'MỤC TIÊU: {goal}\nNGỮ CẢNH: {json.dumps(context, ensure_ascii=False)}'
        history: list[str] = []
        deadline = time.monotonic() + 120
        for iteration in range(1, max_iterations + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(self.llm_router.generate_completion(
                    system_prompt=system_prompt,
                    user_prompt=prefix + '\n' + '\n'.join(history)[-20000:] + f'\nBƯỚC {iteration}/{max_iterations}',
                    temperature=0.2), timeout=min(60, remaining))
            except Exception as error:
                logger.warning('Agent provider failed: %s', error)
                trajectory.append(AgentStep(step_index=iteration, thought='Provider failed', observation=str(error)[:1500], is_error=True))
                return AgentExecutionResult(goal=goal, final_answer='LLM provider failed; no completion verified.',
                    trajectory=trajectory, total_steps=len(trajectory), success=False, state='FAILED', jobs=jobs)
            try:
                decision = AgentDecision.model_validate_json(self._clean_json_text(raw))
            except (ValueError, TypeError, AttributeError) as error:
                observation = 'Invalid decision structure: ' + str(error)[:1500]
                trajectory.append(AgentStep(step_index=iteration, thought='Validate response and retry', observation=observation, is_error=True))
                history.append(observation + '. Return exactly one valid action or final_answer JSON object.')
                continue
            if decision.final_answer:
                pending, failed = False, unresolved_error
                verified_jobs = []
                for submitted in jobs:
                    state = await job_status(submitted)
                    verified_jobs.append(bounded_observation(state))
                    pending |= state['status'] in {'QUEUED', 'RUNNING'}
                    failed |= state['status'] in {'FAILED', 'CANCELLED'}
                    if state['status'] == 'SUCCEEDED' and submitted.get('expected_artifact'):
                        failed |= not await verify_artifact(submitted['project_id'], submitted['expected_artifact'])
                if expected and not pending:
                    failed |= not await verify_artifact(project_id, expected)
                completion = 'FAILED' if failed else 'PENDING' if pending else 'COMPLETED'
                answer = decision.final_answer if completion == 'COMPLETED' else (
                    'Jobs are queued or running; inspect job status before claiming completion.' if completion == 'PENDING'
                    else 'Completion was not verified; inspect tool/job errors and retry.')
                trajectory.append(AgentStep(step_index=iteration, thought=decision.thought,
                    observation={'state': completion}, is_error=failed))
                return AgentExecutionResult(goal=goal, final_answer=answer, trajectory=trajectory,
                    total_steps=len(trajectory), success=completion == 'COMPLETED', state=completion, jobs=verified_jobs)
            arguments = dict(decision.action_input)
            tool = self.toolkit.get_tool(decision.action)
            if project_id and tool and 'project_id' in tool.input_model.model_fields:
                if arguments.get('project_id', project_id) != project_id:
                    arguments['project_id'] = '__context_project_mismatch__'
                else:
                    arguments['project_id'] = project_id
            try:
                if arguments.get('project_id') == '__context_project_mismatch__':
                    raise ValueError('Action project_id differs from the bound context')
                result = await asyncio.wait_for(self.toolkit.execute(decision.action, arguments),
                    timeout=max(.01, min(45, deadline - time.monotonic())))
                observation = bounded_observation(result)
                unresolved_error = not result.get('success', True)
                if result.get('status') == 'QUEUED' and result.get('job_id'):
                    kind = {'burn_video_subtitles': 'burned_video', 'dub_project_video': 'dubbed_video',
                            'extract_and_transcribe_audio': 'transcript', 'start_project_pipeline': 'translated_cues'}.get(decision.action)
                    jobs.append({'project_id': result['project_id'], 'job_id': result['job_id'], 'expected_artifact': kind})
                trajectory.append(AgentStep(step_index=iteration, thought=decision.thought, action=decision.action,
                    action_input=bounded_observation(arguments), observation=observation, is_error=unresolved_error))
                history.append(f'Action: {decision.action}\nObservation: {json.dumps(observation, ensure_ascii=False)[:6000]}')
            except Exception as error:
                logger.warning('Agent tool %s failed: %s', decision.action, error)
                unresolved_error = True
                observation = str(error)[:1500]
                trajectory.append(AgentStep(step_index=iteration, thought=decision.thought, action=decision.action,
                    action_input=bounded_observation(arguments), observation=observation, is_error=True))
                history.append(f'Action: {decision.action} ERROR: {observation}. Correct arguments or use a different valid tool.')
        return AgentExecutionResult(goal=goal, final_answer='Iteration/time budget reached; completion not verified.',
            trajectory=trajectory, total_steps=len(trajectory), success=False, state='PENDING' if jobs and not unresolved_error else 'FAILED', jobs=jobs)


agent_runner = OneFLAgentRunner()
