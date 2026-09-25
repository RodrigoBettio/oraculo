import asyncio
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from ingestion.video_processor import VideoProcessor, ProcessingTier
from models.knowledge import VideoDocument

def test_process_video_is_not_coroutine_function():
    """Garante que process_video é síncrono para funcionar corretamente com asyncio.to_thread."""
    assert not inspect.iscoroutinefunction(VideoProcessor.process_video), (
        "process_video não deve ser async def, pois ao ser executado em asyncio.to_thread "
        "ele retornaria uma coroutine sem executá-la, gerando AttributeError em doc.duration_seconds."
    )

@pytest.mark.anyio
async def test_process_video_in_thread():
    """Garante que rodar process_video em asyncio.to_thread retorna VideoDocument diretamente."""
    vp = VideoProcessor()
    
    mock_doc = VideoDocument(
        video_id="test_video",
        file_name="test.mp4",
        group_name="Test Group",
        duration_seconds=120.0,
        title="Aula Teste",
        summary="Resumo de teste",
        topics=["Tópico 1"],
        full_markdown="# Aula Teste"
    )

    with patch.object(vp, "process_video", return_value=mock_doc):
        doc = await asyncio.to_thread(
            vp.process_video,
            video_path=Path("dummy.mp4"),
            group_name="Test Group",
            video_id="test_video",
            tier=ProcessingTier.AUDIO_ONLY
        )
        assert not inspect.iscoroutine(doc)
        assert isinstance(doc, VideoDocument)
        assert doc.duration_seconds == 120.0
