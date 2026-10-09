import pytest
import io
from pathlib import Path
from fastapi import UploadFile
from starlette.datastructures import Headers
from app.services.storage_service import storage_service


@pytest.mark.asyncio
async def test_save_upload_file_stream(tmp_path):
    project_id = "test_proj_stream_001"
    
    # Create a mock 16MB content payload across multiple chunks
    chunk_data = b"X" * (1024 * 1024 * 2)  # 2MB chunk
    total_chunks = 8  # 16MB total
    payload = chunk_data * total_chunks
    
    file_io = io.BytesIO(payload)
    upload_file = UploadFile(
        file=file_io,
        filename="test_stream_video.mp4",
        headers=Headers({"content-type": "video/mp4"})
    )
    
    # Save using stream with 4MB chunk size
    saved_path = await storage_service.save_upload_file_stream(
        project_id=project_id,
        upload_file=upload_file,
        chunk_size=1024 * 1024 * 4
    )
    
    assert saved_path.exists()
    assert saved_path.stat().st_size == len(payload)
    
    # Clean up test output
    try:
        saved_path.unlink()
        saved_path.parent.rmdir()
    except Exception:
        pass
