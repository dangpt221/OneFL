"""OneFL Agent API Router.

Exposes RESTful endpoints for discovering agent tools, executing tools directly,
and running multi-turn autonomous ReAct agent loops.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.agent.tools import agent_toolkit
from app.agent.agent_runner import agent_runner, AgentExecutionResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent"])


class ExecuteToolRequest(BaseModel):
    tool_name: str = Field(..., description="Tên công cụ muốn thực thi")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Các tham số truyền vào công cụ")


class AgentChatRequest(BaseModel):
    goal: str = Field(..., description="Yêu cầu hoặc mục tiêu phân công cho Agent")
    context: Optional[Dict[str, Any]] = Field(None, description="Bối cảnh dữ liệu phụ trợ (project_id, video_path, v.v.)")
    max_iterations: int = Field(5, ge=1, le=10, description="Giới hạn số bước suy luận ReAct (1-10)")


@router.get("/tools", summary="Danh sách toàn bộ Agent Tools và Function Calling Schemas")
async def list_agent_tools() -> Dict[str, Any]:
    """Trả về toàn bộ danh mục công cụ của OneFL Agent kèm schema JSON Function Calling."""
    tools_list = []
    for tool in agent_toolkit.list_tools():
        tools_list.append({
            "name": tool.name,
            "description": tool.description,
            "function_calling_schema": tool.to_function_calling_schema()
        })
    return {
        "total_tools": len(tools_list),
        "tools": tools_list
    }


@router.post("/execute-tool", summary="Thực thi đơn lẻ một Agent Tool")
async def execute_tool(req: ExecuteToolRequest) -> Dict[str, Any]:
    """Thực thi trực tiếp một tool bằng tên và bộ tham số truyền vào."""
    try:
        result = await agent_toolkit.execute(req.tool_name, req.arguments)
        return {
            "success": True,
            "tool_name": req.tool_name,
            "result": result
        }
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error executing tool '{req.tool_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi thực thi tool: {str(e)}"
        )


@router.post("/chat", response_model=AgentExecutionResult, summary="Chạy chu trình Agent ReAct tự trị")
async def agent_chat(req: AgentChatRequest) -> AgentExecutionResult:
    """Gửi mục tiêu tới OneFL Agent Runner để tự động suy luận, chọn công cụ và xử lý."""
    try:
        result = await agent_runner.run(
            goal=req.goal,
            context=req.context,
            max_iterations=req.max_iterations
        )
        return result
    except Exception as e:
        logger.error(f"Agent chat execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent Runner gặp sự cố: {str(e)}"
        )
