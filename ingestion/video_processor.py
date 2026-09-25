import os
import json
import subprocess
import shutil
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

from google import genai
from google.genai import types

from config import settings
from models.knowledge import VideoDocument, TranscriptSegment, CodeSnippet, ProcessingTier

class VideoProcessor:
    def __init__(self, api_key: Optional[str] = None):
        if api_key:
            self.api_keys = [api_key]
        else:
            self.api_keys = settings.GEMINI_API_KEYS
        self.current_key_idx = 0
        self.client = None
        if self.api_keys:
            self.client = genai.Client(api_key=self.api_keys[0])

    def _ensure_client(self):
        if not self.client:
            if not self.api_keys:
                self.api_keys = settings.GEMINI_API_KEYS
            if not self.api_keys:
                raise ValueError("Nenhuma GEMINI_API_KEY foi configurada no .env!")
            self.client = genai.Client(api_key=self.api_keys[0])

    def rotate_key(self) -> str:
        """Rotaciona automaticamente para a próxima chave de API do pool."""
        if not self.api_keys or len(self.api_keys) <= 1:
            return ""
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        next_key = self.api_keys[self.current_key_idx]
        self.client = genai.Client(api_key=next_key)
        print(f"🔄 Rotacionando chave Gemini API: Chave #{self.current_key_idx + 1} de {len(self.api_keys)} ativa.")
        return next_key

    def get_real_video_duration(self, video_path: Path) -> float:
        """Lê a duração exata do arquivo MP4 usando ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if res.returncode == 0 and res.stdout.strip():
            try:
                return float(res.stdout.strip())
            except ValueError:
                pass
        return 0.0

    def extract_audio(self, video_path: Path, output_audio_path: Optional[Path] = None) -> Path:
        """Extrai o áudio compactado em MP3 a partir do vídeo MP4 usando ffmpeg."""
        if not output_audio_path:
            output_audio_path = video_path.with_suffix(".mp3")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "4",
            str(output_audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"Erro ao extrair áudio com ffmpeg: {result.stderr}")
        
        return output_audio_path

    def extract_keyframes_scene_change(self, video_path: Path, output_dir: Path, interval_seconds: int = 20) -> List[Path]:
        """
        Extrai frames representativos a cada intervalo de segundos (padrão: 20s).
        Garante a captura estável de telas de código e slides com redução de 95% dos tokens.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_pattern = output_dir / "frame_%04d.jpg"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"fps=1/{interval_seconds},scale=1280:-2",
            "-pix_fmt", "yuvj420p",
            "-q:v", "3",
            str(frame_pattern)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"Erro ao extrair frames com ffmpeg: {result.stderr}")

        return sorted(list(output_dir.glob("frame_*.jpg")))

    def process_video(
        self,
        video_path: Path,
        group_name: str,
        video_id: str,
        tier: ProcessingTier = ProcessingTier.AUDIO_ONLY,
        telegram_message_id: Optional[int] = None,
        theme_name: Optional[str] = None,
        companion_files: Optional[List[Any]] = None
    ) -> VideoDocument:
        """Processa um vídeo usando a API multimodal do Gemini nos 2 Tiers configuráveis."""
        self._ensure_client()
        temp_dir = settings.DATA_DIR / "temp" / video_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Extração do Áudio
            audio_path = temp_dir / "audio.mp3"
            self.extract_audio(video_path, audio_path)

            contents = []
            
            # Upload do áudio para a File API do Gemini
            uploaded_audio = self.client.files.upload(file=str(audio_path))
            contents.append(uploaded_audio)

            # 2. Se for Modo Profundo, extrai e anexa keyframes visuais
            if tier == ProcessingTier.MULTIMODAL_OCR:
                frames_dir = temp_dir / "frames"
                keyframes = self.extract_keyframes_scene_change(video_path, frames_dir)
                # Limita a no máximo 20 frames representativos para controle rigoroso de tokens
                sampled_frames = keyframes[:20]
                for frame_file in sampled_frames:
                    uploaded_frame = self.client.files.upload(file=str(frame_file))
                    contents.append(uploaded_frame)

            # 3. Prompt estruturado para gerar conhecimento e código contextualizado
            theme_ctx = f"\nTema / Módulo: '{theme_name}'" if theme_name else ""
            comp_names = []
            if companion_files:
                for cf in companion_files:
                    if isinstance(cf, dict):
                        comp_names.append(cf.get("name") or cf.get("file_name") or str(cf))
                    else:
                        comp_names.append(str(cf))
            comp_ctx = f"\nArquivos complementares anexados a este módulo: {', '.join(comp_names)}" if comp_names else ""

            prompt = f"""
Você é o processador de conhecimento do Oráculo. Analise o conteúdo deste vídeo do curso '{group_name}'.{theme_ctx}{comp_ctx}
Tier de análise: {tier.value}

Instruções:
1. Extraia o título da aula e um resumo geral claro considerando o tema '{theme_name or group_name}'.
2. Liste os principais tópicos abordados.
3. Se houver relação com os arquivos complementares do módulo ({', '.join(comp_names) if comp_names else 'nenhum'}), contextualize a explicação teórica e prática.
4. Crie segmentos com timestamps (ex: '00:00 - 05:20') transcrevendo as explicações chave.
5. Se houver código mostrado na tela ou ditado, extraia o código EXATO no bloco apropriado com linguagem e timestamp.
6. Gere uma versão completa em formato Markdown rica, pronta para ser lida por agentes ou exportada para o NotebookLM.

Retorne estritamente um JSON com a seguinte estrutura:
{{
  "title": "Título da Aula",
  "summary": "Resumo abrangente do vídeo",
  "topics": ["Tópico 1", "Tópico 2"],
  "segments": [
    {{
      "start_time": "00:00",
      "end_time": "04:30",
      "text": "Explicação falada...",
      "visual_description": "O que aparecia na tela...",
      "code_snippets": [
        {{
          "timestamp": "02:15",
          "language": "html/typescript/etc",
          "code": "código extraído",
          "description": "Explicação do código"
        }}
      ]
    }}
  ],
  "full_markdown": "# Título\\n\\n## Resumo\\n...\\n## Código e Timestamps\\n..."
}}
"""
            contents.append(prompt)

            # Chamada ao modelo Gemini Flash com retry e fallback resiliente
            models_to_try = settings.STUDY_MODELS
            response = None
            last_error = None

            for model_name in models_to_try:
                for attempt in range(4):
                    try:
                        response = self.client.models.generate_content(
                            model=model_name,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                temperature=0.2
                            )
                        )
                        if response and response.text:
                            if hasattr(response, "usage_metadata") and response.usage_metadata:
                                try:
                                    from utils.token_tracker import record_tokens
                                    record_tokens(
                                        source="study",
                                        details=f"{group_name} / {video_id} ({tier.value})",
                                        prompt_tokens=getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                                        output_tokens=getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                                        total_tokens=getattr(response.usage_metadata, "total_token_count", 0) or 0,
                                        model=model_name
                                    )
                                except Exception:
                                    pass
                            break
                    except Exception as e:
                        last_error = e
                        err_str = str(e).upper()
                        import time
                        # Se for 503 / 429 ou alta demanda temporária, aplica backoff progressivo
                        backoff = 4 * (attempt + 1)
                        time.sleep(backoff)
                if response and response.text:
                    break

            if not response or not response.text:
                raise RuntimeError(f"Falha ao processar vídeo no Gemini: {last_error}")

            def repair_and_parse_json(raw: str) -> dict:
                import re
                t = raw.strip()
                if t.startswith("```"):
                    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
                if t.endswith("```"):
                    t = re.sub(r"\s*```$", "", t)
                t = t.strip()

                first_brace = t.find("{")
                last_brace = t.rfind("}")
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    t = t[first_brace:last_brace + 1]

                try:
                    return json.loads(t, strict=False)
                except Exception:
                    pass

                # Sanitiza caracteres de controle
                sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', t)
                try:
                    return json.loads(sanitized, strict=False)
                except Exception:
                    pass

                # Remove trailing commas
                fixed = re.sub(r',\s*([\}\]])', r'\1', sanitized)
                # Corrige vírgulas faltantes entre elementos adjacentes
                fixed = re.sub(r'\}\s*\{', '},{', fixed)
                fixed = re.sub(r'\]\s*\[', '],[', fixed)
                try:
                    return json.loads(fixed, strict=False)
                except Exception:
                    pass

                # Tenta balancear chaves e colchetes se foi truncado no final
                open_curly = fixed.count("{") - fixed.count("}")
                open_square = fixed.count("[") - fixed.count("]")
                if open_curly > 0 or open_square > 0:
                    balanced = re.sub(r',\s*"[^"]*"?$', '', fixed)
                    balanced += ("]" * max(0, open_square)) + ("}" * max(0, open_curly))
                    try:
                        return json.loads(balanced, strict=False)
                    except Exception:
                        pass

                return json.loads(t, strict=False)

            data = repair_and_parse_json(response.text)


            # Extração dos códigos acumulados
            all_codes = []
            segments = []
            for seg in data.get("segments", []):
                seg_codes = [CodeSnippet(**c) for c in seg.get("code_snippets", [])]
                all_codes.extend(seg_codes)
                segments.append(TranscriptSegment(
                    start_time=seg.get("start_time", "00:00"),
                    end_time=seg.get("end_time", "00:00"),
                    text=seg.get("text", ""),
                    visual_description=seg.get("visual_description"),
                    code_snippets=seg_codes
                ))

            real_duration = self.get_real_video_duration(video_path)

            doc = VideoDocument(
                video_id=video_id,
                file_name=video_path.name,
                group_name=group_name,
                theme_name=theme_name,
                companion_files=comp_names,
                telegram_message_id=telegram_message_id,
                duration_seconds=real_duration,
                tier_used=tier,
                title=data.get("title", video_path.stem),
                summary=data.get("summary", ""),
                topics=data.get("topics", []),
                segments=segments,
                extracted_codes=all_codes,
                full_markdown=data.get("full_markdown", "")
            )

            # Salva o resultado indexado no diretório processado do grupo
            group_store = settings.PROCESSED_DIR / group_name
            group_store.mkdir(parents=True, exist_ok=True)
            
            with open(group_store / f"{video_id}.json", "w", encoding="utf-8") as f:
                f.write(doc.model_dump_json(indent=2))

            with open(group_store / f"{video_id}.md", "w", encoding="utf-8") as f:
                f.write(doc.full_markdown)

            return doc

        finally:
            # Limpeza de arquivos temporários de frames e áudio
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def process_pdf(
        self,
        pdf_path: Path,
        group_name: str,
        pdf_id: str,
        telegram_message_id: Optional[int] = None,
        theme_name: Optional[str] = None
    ) -> tuple[VideoDocument, Dict[str, Any]]:
        """
        Processa um arquivo PDF multimodal com Gemini Flash:
        - Realiza OCR e extração profunda de texto, diagramas, códigos e padrões de design.
        - Executa Curadoria Inteligente para decidir se o material deve ser preservado no Cofre de Documentos
          (padrões de design, manuais, guias arquiteturais) ou descartado (resumos efêmeros).
        """
        self._ensure_client()
        temp_dir = settings.DATA_DIR / "temp" / pdf_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Leitura nativa de PDF com OCR Multimodal:
            # Para arquivos de até 20MB, envia diretamente como bytes inline (Part.from_bytes),
            # exatamente como o NotebookLM faz. Isso elimina 100% dos problemas de encoding ASCII
            # de cabeçalhos HTTP do client.files.upload e acelera o processamento!
            file_size = pdf_path.stat().st_size if pdf_path.exists() else 0
            if file_size > 0 and file_size <= 20 * 1024 * 1024:
                pdf_data = pdf_path.read_bytes()
                pdf_part = types.Part.from_bytes(data=pdf_data, mime_type="application/pdf")
            else:
                # Fallback para arquivos maiores que 20MB via File API com nome ASCII seguro
                safe_ascii_name = f"doc_{re.sub(r'[^a-zA-Z0-9_.-]', '_', pdf_id)}.pdf"
                clean_pdf_file = temp_dir / safe_ascii_name
                shutil.copy2(pdf_path, clean_pdf_file)
                pdf_part = self.client.files.upload(file=str(clean_pdf_file))
            
            theme_ctx = f"\nTema/Módulo de estudo: {theme_name}" if theme_name else ""
            
            prompt = f"""
Você é o Curador e Analista Sênior de Conhecimento do Oráculo.{theme_ctx}
Você está analisando o documento/material PDF: '{pdf_path.name}' do curso/canal '{group_name}'.

Realize uma leitura profunda e criteriosa via OCR em todo o documento:
1. Extraia o Título do Documento e um Resumo Geral robusto.
2. Liste os Tópicos e habilidades ensinadas.
3. Se houver código, esquemas ou diagramas representados no PDF, extraia com precisão no bloco de código correto.
4. Gere um Documento Markdown Completo, rico, técnico e didático.
5. CURADORIA INTELIGENTE PARA O COFRE DE DOCUMENTOS (Vault):
   Avalie a natureza e a utilidade futura deste material para a equipe de agentes e para o usuário:
   - Defina "vault_retention": "PERMANENTE" ou "EFEMERO"
     * "PERMANENTE": Se contiver padrões de design (design patterns, UI/UX, arquitetura de software, diagramas de sistema, especificações técnicas, frameworks, manuais reutilizáveis, cheat sheets). Materiais que servem como catálogo ou referência constante.
     * "EFEMERO": Se for apenas um resumo redundante de aula, anotações rápidas de apoio que já estão ditas no vídeo, material de boas-vindas ou avisos descartáveis.
   - Defina "vault_category": Categoria sugerida se for permanente (ex: "Padrões de Design", "Arquitetura de Software", "Guia Técnico", "Frontend", "Backend", "Estratégia")
   - Defina "curation_rationale": Explique sucintamente (1-2 frases) o motivo da decisão de curadoria.
   - Defina "estimated_reading_minutes": Minutos estimados de estudo deste material (ex: 20, 30).

Retorne estritamente um JSON com a seguinte estrutura:
{{
  "title": "Título Oficial do Material",
  "summary": "Resumo analítico profundo do material",
  "topics": ["Tópico 1", "Tópico 2", "Padrão X"],
  "extracted_codes": [
    {{
      "timestamp": "00:00",
      "language": "typescript/python/css/etc",
      "code": "código ou especificação extraída",
      "description": "Explicação do padrão ou código"
    }}
  ],
  "full_markdown": "# Título\\n\\n## Resumo Executivo\\n...\\n## Padrões de Design & Arquitetura\\n...",
  "vault_retention": "PERMANENTE",
  "vault_category": "Padrões de Design",
  "curation_rationale": "Contém especificações e diagramas reutilizáveis de arquitetura de software.",
  "estimated_reading_minutes": 25
}}
"""
            contents = [pdf_part, prompt]

            models_to_try = settings.STUDY_MODELS
            response = None
            last_error = None

            for model_name in models_to_try:
                for attempt in range(4):
                    try:
                        response = self.client.models.generate_content(
                            model=model_name,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                temperature=0.2
                            )
                        )
                        if response and response.text:
                            if hasattr(response, "usage_metadata") and response.usage_metadata:
                                try:
                                    from utils.token_tracker import record_tokens
                                    record_tokens(
                                        source="study_pdf",
                                        details=f"{group_name} / {pdf_path.name} (PDF OCR)",
                                        prompt_tokens=getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                                        output_tokens=getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                                        total_tokens=getattr(response.usage_metadata, "total_token_count", 0) or 0,
                                        model=model_name
                                    )
                                except Exception:
                                    pass
                            break
                    except Exception as e:
                        last_error = e
                        import time
                        time.sleep(1.5 * (attempt + 1))
                if response and response.text:
                    break

            if not response or not response.text:
                raise RuntimeError(f"Falha ao processar PDF com Gemini: {last_error}")

            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text.split("```json", 1)[1].rsplit("```", 1)[0].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text.split("```", 1)[1].rsplit("```", 1)[0].strip()

            data = json.loads(raw_text)

            all_codes = []
            for sc in data.get("extracted_codes", []):
                all_codes.append(CodeSnippet(
                    timestamp=sc.get("timestamp", "00:00"),
                    language=sc.get("language", "text"),
                    code=sc.get("code", ""),
                    description=sc.get("description", "")
                ))

            reading_mins = data.get("estimated_reading_minutes", 20) or 20
            duration_sec = float(reading_mins * 60)

            curation_result = {
                "is_valuable_for_vault": data.get("vault_retention", "").upper() == "PERMANENTE",
                "vault_category": data.get("vault_category", "Padrões & Referência"),
                "curation_rationale": data.get("curation_rationale", "Material curado automaticamente."),
                "reading_minutes": reading_mins
            }

            doc = VideoDocument(
                video_id=pdf_id,
                file_name=pdf_path.name,
                group_name=group_name,
                theme_name=theme_name,
                telegram_message_id=telegram_message_id,
                duration_seconds=duration_sec,
                tier_used=ProcessingTier.MULTIMODAL_OCR,
                title=data.get("title", pdf_path.stem),
                summary=data.get("summary", ""),
                topics=data.get("topics", []),
                segments=[],
                extracted_codes=all_codes,
                full_markdown=data.get("full_markdown", "")
            )

            # Salva no repositório local de processados
            group_store = settings.PROCESSED_DIR / group_name
            group_store.mkdir(parents=True, exist_ok=True)
            with open(group_store / f"{pdf_id}.json", "w", encoding="utf-8") as f:
                f.write(doc.model_dump_json(indent=2))
            with open(group_store / f"{pdf_id}.md", "w", encoding="utf-8") as f:
                f.write(doc.full_markdown)

            return doc, curation_result

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

