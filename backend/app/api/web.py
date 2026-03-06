"""S14.2 — Web Upload API.

POST /api/translate: accepts a prescription image upload + language_code,
runs the full pipeline, and returns JSON with translation results.
No Twilio, no WhatsApp, no session management — direct HTTP API.
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from loguru import logger

router = APIRouter()

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/translate")
async def web_translate(
    image: UploadFile = File(...),
    language_code: str = Form(...),
):
    """Upload a prescription image and receive a translated summary.

    Accepts multipart/form-data with:
    - image: prescription photo (JPEG, PNG)
    - language_code: one of the 22 supported Indian language codes
    """
    # Lazy imports to avoid module-level Settings() trigger
    from backend.app.services.whatsapp import SUPPORTED_LANGUAGES

    request_id = str(uuid.uuid4())

    with logger.contextualize(request_id=request_id):
        # --- Validate language_code ---
        if language_code not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language_code: '{language_code}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_LANGUAGES.keys()))}",
            )

        lang_info = SUPPORTED_LANGUAGES[language_code]
        language_name = lang_info["name"]

        # --- Validate image ---
        content_type = image.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: '{content_type}'. Only image files are accepted.",
            )

        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Uploaded image is empty.")

        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Image too large ({len(image_bytes)} bytes). Max: {MAX_IMAGE_SIZE} bytes.",
            )

        logger.info(
            "Web translate request: language={}, image_size={}, content_type={}",
            language_code,
            len(image_bytes),
            content_type,
        )

        start = time.monotonic()

        try:
            return await _run_web_pipeline(
                image_bytes=image_bytes,
                content_type=content_type,
                language_code=language_code,
                language_name=language_name,
                request_id=request_id,
                start=start,
            )
        except HTTPException:
            raise
        except Exception as exc:
            # Import here to check exception types
            from backend.app.services.extraction import (
                ExtractionError,
                ImageNotReadableError,
                NotMedicalDocumentError,
            )
            from backend.app.services.translation import TranslationError

            if isinstance(exc, NotMedicalDocumentError):
                raise HTTPException(status_code=422, detail=str(exc))
            if isinstance(exc, ImageNotReadableError):
                raise HTTPException(status_code=422, detail=str(exc))
            if isinstance(exc, (ExtractionError, TranslationError)):
                logger.error("Pipeline error: {}", type(exc).__name__)
                raise HTTPException(status_code=500, detail="Failed to process prescription.")

            logger.exception("Unexpected error in web translate")
            raise HTTPException(status_code=500, detail="Internal server error.")


async def _run_web_pipeline(
    image_bytes: bytes,
    content_type: str,
    language_code: str,
    language_name: str,
    request_id: str,
    start: float,
):
    """Execute the full pipeline and return a WebTranslationResponse dict."""
    from backend.app.api.webhooks import _format_audio_text
    from backend.app.models.schemas import WebMedicineDetail, WebTranslationResponse
    from backend.app.services.drug_lookup import enrich_prescription
    from backend.app.services.extraction import extract_prescription_from_bytes
    from backend.app.services.glossary import format_glossary_context, lookup_terms
    from backend.app.services.tts import generate_and_deliver_audio
    from backend.app.services.translation import simplify_and_translate

    # Step 1: Extract prescription from image bytes
    logger.info("Pipeline: extraction")
    prescription = await extract_prescription_from_bytes(
        image_bytes=image_bytes,
        content_type=content_type,
        request_id=request_id,
    )

    # Step 2: Drug enrichment (needs Redis)
    logger.info("Pipeline: drug enrichment")
    drug_info_list = []
    redis_client = None
    try:
        from backend.app.db.redis import _redis_client

        redis_client = _redis_client
    except Exception:
        pass

    if redis_client:
        drug_info_list = await enrich_prescription(
            redis_client=redis_client,
            prescription=prescription,
            request_id=request_id,
        )

    # Step 3: Glossary lookup
    logger.info("Pipeline: glossary lookup")
    glossary_context = ""
    if redis_client:
        medicine_terms = [m.medicine_name for m in prescription.medicines]
        glossary_entries = await lookup_terms(medicine_terms, language_code, redis_client)
        glossary_context = format_glossary_context(glossary_entries, language_name)

    # Step 4: Translate with Claude
    logger.info("Pipeline: translation")
    translation = await simplify_and_translate(
        prescription=prescription,
        language_name=language_name,
        language_code=language_code,
        drug_info_list=drug_info_list,
        glossary_context=glossary_context,
        request_id=request_id,
    )

    # Step 5: TTS (Edge TTS fallback if Bhashini not available)
    logger.info("Pipeline: TTS")
    audio_text = _format_audio_text(
        prescription=prescription,
        translation=translation,
        language_name=language_name,
    )
    audio_url = await generate_and_deliver_audio(
        text=audio_text,
        language_code=language_code,
        request_id=request_id,
    )

    latency_ms = int((time.monotonic() - start) * 1000)

    # Build response
    medicines = []
    for i, med in enumerate(prescription.medicines):
        drug = drug_info_list[i] if i < len(drug_info_list) and drug_info_list[i] else None
        medicines.append(
            WebMedicineDetail(
                name=med.medicine_name,
                dosage=med.dosage,
                frequency=med.frequency,
                duration=med.duration,
                confidence=med.confidence,
                purpose=drug.purpose_en if drug else None,
                side_effects=drug.side_effects_en if drug else None,
            )
        )

    logger.info("Web translate complete: latency_ms={}", latency_ms)

    return WebTranslationResponse(
        request_id=request_id,
        language_code=language_code,
        language_name=language_name,
        medicines=medicines,
        translated_text=translation.translated_text,
        per_medicine_summaries=translation.per_medicine_summaries,
        disclaimer=translation.disclaimer,
        audio_url=audio_url,
        latency_ms=latency_ms,
    )
