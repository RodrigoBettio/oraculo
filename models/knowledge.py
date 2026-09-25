from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class ProcessingTier(str, Enum):
    AUDIO_ONLY = "audio_only"             # Modo Econômico: Transcrição rápida de áudio
    MULTIMODAL_OCR = "multimodal_ocr"     # Modo Profundo: Áudio + Captura visual de código e slides

class CodeSnippet(BaseModel):
    timestamp: str                         # Ex: "14:22"
    language: str = "javascript"           # Ex: "typescript", "html", "python", "css"
    code: str
    description: Optional[str] = None      # O que estava sendo demonstrado na tela

class TranscriptSegment(BaseModel):
    start_time: str                        # Ex: "05:10"
    end_time: str                          # Ex: "07:30"
    text: str                              # Transcrição do que foi falado
    visual_description: Optional[str] = None # O que aparecia no slide/tela
    code_snippets: List[CodeSnippet] = Field(default_factory=list)

class VideoDocument(BaseModel):
    video_id: str
    file_name: str
    group_name: str
    telegram_message_id: Optional[int] = None
    duration_seconds: float = 0.0
    tier_used: ProcessingTier = ProcessingTier.AUDIO_ONLY
    
    # Conteúdo Consolidado
    title: str
    summary: str
    theme_name: Optional[str] = None
    companion_files: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    segments: List[TranscriptSegment] = Field(default_factory=list)
    extracted_codes: List[CodeSnippet] = Field(default_factory=list)
    
    # Documento Markdown pronto para consumo do Agente ou exportação NotebookLM
    full_markdown: str
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
