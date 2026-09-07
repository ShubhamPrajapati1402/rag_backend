from typing import Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["Voice (STT & TTS)"])
voice_service = VoiceService()


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text content to synthesize into speech")
    voice: Optional[str] = Field(
        default=None,
        description="Neural voice identifier (e.g., en-US-ChristopherNeural, en-IN-PrabhatNeural)",
    )
    rate: Optional[str] = Field(default="+0%", description="Speech speed adjustment (e.g. +0%, +15%, -10%)")
    pitch: Optional[str] = Field(default="+0Hz", description="Voice pitch adjustment (e.g. +0Hz, +5Hz)")


@router.post("/stt", summary="Transcribe Speech to Text (STT)")
async def speech_to_text(
    file: UploadFile = File(..., description="Audio file blob recorded from client microphone"),
    language: Optional[str] = Query(None, description="Optional ISO-639-1 language code (e.g. 'en')"),
):
    """Transcribe an in-memory audio recording to text using Groq Whisper Large v3 Turbo.
    
    Supports formats: webm, wav, mp3, ogg, m4a, flac.
    """
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file uploaded",
        )

    # Read binary content
    try:
        audio_bytes = await file.read()
    except Exception as e:
        logger.error(f"Failed to read incoming audio stream: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read uploaded audio stream",
        )

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty",
        )

    filename = file.filename or "audio.webm"
    try:
        transcript = await voice_service.transcribe_audio(
            audio_bytes=audio_bytes,
            filename=filename,
            language=language,
        )
        return {
            "success": True,
            "text": transcript,
            "filename": filename,
        }
    except Exception as e:
        logger.error(f"STT Error processing audio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech transcription failed: {str(e)}",
        )


@router.get("/tts", summary="Stream Text to Speech (TTS)")
async def text_to_speech_get(
    text: str = Query(..., min_length=1, description="Text to synthesize into speech"),
    voice: Optional[str] = Query(None, description="Voice ID (defaults to settings.VOICE_DEFAULT_TTS_VOICE)"),
    rate: Optional[str] = Query("+0%", description="Speaking speed"),
    pitch: Optional[str] = Query("+0Hz", description="Voice pitch"),
):
    """Directly stream neural MP3 audio to HTML5 <audio> elements for instant playback."""
    cleaned_text = voice_service.clean_text_for_tts(text)
    if not cleaned_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided text does not contain readable speech content",
        )

    try:
        audio_stream = voice_service.synthesize_speech_stream(
            text=cleaned_text,
            voice=voice or settings.VOICE_DEFAULT_TTS_VOICE,
            rate=rate or "+0%",
            pitch=pitch or "+0Hz",
        )
        return StreamingResponse(
            audio_stream,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=speech.mp3",
                "Cache-Control": "no-cache",
                "Accept-Ranges": "bytes",
            },
        )
    except Exception as e:
        logger.error(f"TTS Stream error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice synthesis failed: {str(e)}",
        )


@router.post("/tts", summary="Synthesize Text to Speech (TTS)")
async def text_to_speech(payload: TTSRequest):
    """Synthesize text into high-fidelity neural MP3 audio stream using Edge-TTS."""
    cleaned_text = voice_service.clean_text_for_tts(payload.text)
    if not cleaned_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided text does not contain readable speech content after markdown sanitization",
        )

    try:
        chosen_voice = payload.voice or settings.VOICE_DEFAULT_TTS_VOICE
        audio_stream = voice_service.synthesize_speech_stream(
            text=cleaned_text,
            voice=chosen_voice,
            rate=payload.rate or "+0%",
            pitch=payload.pitch or "+0Hz",
        )
        return StreamingResponse(
            audio_stream,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=speech.mp3",
                "Cache-Control": "no-cache",
                "Accept-Ranges": "bytes",
                "X-Voice-Id": chosen_voice,
            },
        )
    except Exception as e:
        logger.error(f"TTS Synthesis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice synthesis failed: {str(e)}",
        )


@router.get("/voices", summary="List Curated Neural Voices")
async def get_voices():
    """Return the list of curated Microsoft neural voices with language, accent, and gender metadata."""
    return {
        "success": True,
        "voices": voice_service.get_curated_voices(),
    }
