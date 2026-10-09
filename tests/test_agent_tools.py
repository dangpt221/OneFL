"""Unit & Integration tests for OneFL Agent Toolkit, Tools, ReAct Runner, and API endpoints."""

import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.agent.tools import agent_toolkit
from app.agent.agent_runner import OneFLAgentRunner, AgentExecutionResult


EXPECTED_TOOLS = [
    "inspect_video_media",
    "extract_and_transcribe_audio",
    "analyze_speaker_profiles",
    "build_relationship_matrix",
    "translate_subtitle_chunk",
    "run_subtitle_guardrails",
    "query_master_glossary",
    "export_subtitles",
    "generate_dubbing_audio",
    "burn_video_subtitles",
]


def test_agent_toolkit_registration():
    """Verify that all 10 tools are registered in AgentToolkit."""
    tools = agent_toolkit.list_tools()
    tool_names = [t.name for t in tools]
    assert len(tools) == 10
    for expected in EXPECTED_TOOLS:
        assert expected in tool_names, f"Tool {expected} must be registered"


def test_agent_toolkit_schemas():
    """Verify OpenAI / Gemini compatible Function Calling Schema generation for each tool."""
    for tool in agent_toolkit.list_tools():
        schema = tool.to_function_calling_schema()
        assert schema["type"] == "function"
        fn = schema["function"]
        assert fn["name"] == tool.name
        assert len(fn["description"]) > 0
        params = fn["parameters"]
        assert params["type"] == "object"
        assert "properties" in params


@pytest.mark.asyncio
async def test_query_master_glossary_tool():
    """Verify query_master_glossary tool execution."""
    res = await agent_toolkit.execute(
        "query_master_glossary",
        {"query": "latency", "limit": 5}
    )
    assert res["query"] == "latency"
    assert "matches" in res
    assert res["total_matches"] >= 1
    first_match = res["matches"][0]
    assert "source_term" in first_match
    assert "target_term" in first_match



@pytest.mark.asyncio
async def test_run_subtitle_guardrails_tool():
    """Verify run_subtitle_guardrails tool execution with simulated LLM response."""
    requested_cues = [
        {"id": 1, "text": "Captain, incoming missile!", "duration": 2.5}
    ]
    raw_response = json.dumps({
        "translations": [
            {"id": 1, "text": "Thuyền trưởng, tên lửa đang lao tới!"}
        ]
    })

    res = await agent_toolkit.execute(
        "run_subtitle_guardrails",
        {
            "requested_cues": requested_cues,
            "llm_raw_response": raw_response
        }
    )
    assert res["is_valid"] is True
    assert res["total_passed"] == 1
    assert len(res["passed_translations"]) == 1
    assert res["passed_translations"][0]["text"] == "Thuyền trưởng, tên lửa đang lao tới!"


@pytest.mark.asyncio
async def test_export_subtitles_tool():
    """Verify export_subtitles tool generation for ASS and SRT."""
    cues = [
        {
            "start_time": "00:00:01,000",
            "end_time": "00:00:04,000",
            "start": 1.0,
            "end": 4.0,
            "text": "Đây là câu thoại phụ đề thử nghiệm.",
            "original_text": "This is a test subtitle."
        }
    ]

    # Test SRT export
    res_srt = await agent_toolkit.execute(
        "export_subtitles",
        {"cues": cues, "format": "srt", "bilingual": False}
    )
    assert res_srt["format"] == "srt"
    assert "00:00:01" in res_srt["content_preview"]
    assert "Đây là câu thoại" in res_srt["content_preview"]

    # Test ASS export
    res_ass = await agent_toolkit.execute(
        "export_subtitles",
        {"cues": cues, "format": "ass", "preset": "cinema"}
    )
    assert res_ass["format"] == "ass"
    assert "[Script Info]" in res_ass["content_preview"]



@pytest.mark.asyncio
async def test_inspect_video_media_missing_file():
    """Verify inspect_video_media graceful error handling when file is not found."""
    res = await agent_toolkit.execute(
        "inspect_video_media",
        {"video_path": "non_existent_video_file_12345.mp4"}
    )
    assert res["status"] == "ERROR"
    assert "không tồn tại" in res["error"]


@pytest.mark.asyncio
async def test_agent_runner_react_loop():
    """Verify ReAct reasoning loop with mocked multi-step LLM responses."""
    mock_router = AsyncMock()
    # Step 1: LLM decides to call query_master_glossary
    # Step 2: LLM observes result and returns final answer
    step_1_resp = json.dumps({
        "thought": "Tôi cần tra cứu thuật ngữ AI trong từ điển chuyên ngành.",
        "action": "query_master_glossary",
        "action_input": {"query": "AI", "limit": 2}
    })
    step_2_resp = json.dumps({
        "thought": "Đã có kết quả tra cứu. Tôi sẽ trả lời người dùng.",
        "final_answer": "AI là Trí tuệ nhân tạo (Artificial Intelligence)."
    })

    mock_router.generate_completion.side_effect = [step_1_resp, step_2_resp]

    runner = OneFLAgentRunner(llm_router=mock_router)
    result: AgentExecutionResult = await runner.run(
        goal="Tra cứu nghĩa của từ AI và giải thích cho tôi",
        max_iterations=3
    )

    assert result.success is True
    assert result.total_steps == 2
    assert "Trí tuệ nhân tạo" in result.final_answer
    assert len(result.trajectory) == 2
    assert result.trajectory[0].action == "query_master_glossary"
    assert result.trajectory[0].observation is not None
    assert result.trajectory[1].action is None


def test_agent_api_endpoints():
    """Verify FastAPI endpoints for Agent Tools discovery and single tool execution."""
    client = TestClient(app)

    # 1. GET /api/v1/agent/tools
    resp = client.get("/api/v1/agent/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tools"] == 10
    names = [t["name"] for t in data["tools"]]
    assert "inspect_video_media" in names
    assert "query_master_glossary" in names

    # 2. POST /api/v1/agent/execute-tool (valid tool)
    exec_resp = client.post(
        "/api/v1/agent/execute-tool",
        json={
            "tool_name": "query_master_glossary",
            "arguments": {"query": "AI", "limit": 3}
        }
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["success"] is True
    assert exec_data["tool_name"] == "query_master_glossary"
    assert "matches" in exec_data["result"]

    # 3. POST /api/v1/agent/execute-tool (nonexistent tool)
    fail_resp = client.post(
        "/api/v1/agent/execute-tool",
        json={
            "tool_name": "non_existent_tool_xyz",
            "arguments": {}
        }
    )
    assert fail_resp.status_code == 404
