import io
import re
from typing import AsyncGenerator, Dict, List, Optional
import edge_tts
from groq import AsyncGroq
from loguru import logger

from app.core.config import settings


class VoiceService:
    """Service providing Speech-to-Text (STT) via Groq Whisper and Text-to-Speech (TTS) via Edge-TTS."""

    def __init__(self):
        self._groq_client: Optional[AsyncGroq] = None

    @property
    def groq_client(self) -> AsyncGroq:
        if self._groq_client is None:
            self._groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        return self._groq_client

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "audio.webm",
        language: Optional[str] = None,
    ) -> str:
        """Transcribe speech audio to text using Groq Whisper Large v3 Turbo."""
        if not audio_bytes or len(audio_bytes) == 0:
            raise ValueError("Audio data is empty")

        try:
            kwargs = {
                "file": (filename, audio_bytes),
                "model": settings.VOICE_STT_MODEL or "whisper-large-v3-turbo",
                "response_format": "json",
                "temperature": 0.0,
            }
            if language:
                kwargs["language"] = language

            transcription = await self.groq_client.audio.transcriptions.create(**kwargs)
            text = transcription.text.strip()

            # Filter out known Whisper silence / background noise hallucinations
            cleaned_lower = re.sub(r"[^\w\s]", "", text.lower()).strip()
            silence_hallucinations = {
                "thank you",
                "thank you very much",
                "thanks for watching",
                "thank you for watching",
                "you",
                "bye",
                "goodbye",
                "subtitles by",
                "subscribe",
                "please subscribe",
                "subscribe to my channel",
                "the end",
            }
            if cleaned_lower in silence_hallucinations:
                logger.info(f"[VoiceSTT] Suppressed Whisper silence hallucination: '{text}'")
                return ""

            return text
        except Exception as e:
            logger.error(f"STT transcription failed: {e}")
            raise RuntimeError(f"Voice transcription failed: {str(e)}") from e

    def clean_text_for_tts(self, text: str) -> str:
        """Sanitize markdown, citations, URLs, and code blocks for fluid, natural speech."""
        if not text:
            return ""

        # Replace markdown code blocks (```python ... ```) with brief spoken placeholder
        cleaned = re.sub(r"```[\w-]*\n[\s\S]*?```", " Code block omitted. ", text)
        # Strip inline code ticks `code` -> code
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        # Strip footnotes / citation badges e.g. [^1], [1], [1, 2]
        cleaned = re.sub(r"\[\^?\d+(?:,\s*\d+)*\]", "", cleaned)
        # Replace markdown links [label](url) -> label
        cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
        # Strip raw URLs
        cleaned = re.sub(r"https?://\S+", "", cleaned)
        # Strip headers and blockquote markers (including indented)
        cleaned = re.sub(r"^\s*#+\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*>\s*", "", cleaned, flags=re.MULTILINE)
        # Strip bullet points and list dashes
        cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
        # Strip bold, italics, strikethrough markdown symbols
        cleaned = re.sub(r"[*_~]", "", cleaned)
        # Strip horizontal rules
        cleaned = re.sub(r"^\s*---+\s*$", "", cleaned, flags=re.MULTILINE)
        # Collapse multiple spaces and newlines
        cleaned = re.sub(r"\n\s*\n+", ". ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    async def synthesize_speech_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize text into streaming MP3 audio chunks via Edge-TTS."""
        cleaned_text = self.clean_text_for_tts(text)
        if not cleaned_text:
            return

        communicate = edge_tts.Communicate(
            text=cleaned_text,
            voice=voice or settings.VOICE_DEFAULT_TTS_VOICE or "en-US-ChristopherNeural",
            rate=rate,
            pitch=pitch,
        )

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    @staticmethod
    def get_curated_voices() -> List[Dict[str, str]]:
        """Return a list of curated high-fidelity neural voices."""
        return [
            {
                "id": "en-US-ChristopherNeural",
                "name": "Christopher",
                "gender": "Male",
                "accent": "US English",
                "tag": "Professional & Authoritative",
            },
            {
                "id": "en-US-JennyNeural",
                "name": "Jenny",
                "gender": "Female",
                "accent": "US English",
                "tag": "Natural & Friendly",
            },
            {
                "id": "en-IN-PrabhatNeural",
                "name": "Prabhat",
                "gender": "Male",
                "accent": "Indian English",
                "tag": "Clear & Professional",
            },
            {
                "id": "en-IN-NeerjaNeural",
                "name": "Neerja",
                "gender": "Female",
                "accent": "Indian English",
                "tag": "Warm & Articulate",
            },
            {
                "id": "en-GB-RyanNeural",
                "name": "Ryan",
                "gender": "Male",
                "accent": "British English",
                "tag": "Refined & Polished",
            },
            {
                "id": "en-GB-SoniaNeural",
                "name": "Sonia",
                "gender": "Female",
                "accent": "British English",
                "tag": "Engaging & Expressive",
            },
        ]
