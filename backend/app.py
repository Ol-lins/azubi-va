"""
Azubi Voice Assistant (azubi-va)
Lambda handler for Text-to-Speech via Amazon Polly.

Notes:
- Supports mp3 / ogg_vorbis / pcm
- Accepts plain text by default; enable SSML via useSsml=true for richer control
- Stores output in S3 and returns a pre-signed URL (private by default)

Author: COLLINS ODURO OBENG 
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from typing import Any, Dict, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# -------- Constants / Config --------
SUPPORTED_FORMATS = {"mp3": ("audio/mpeg", "mp3"),
                     "ogg_vorbis": ("audio/ogg", "ogg_vorbis"),
                     "pcm": ("audio/wave", "pcm")}
DEFAULT_VOICE = "Joanna"
MAX_CHARS = int(os.getenv("MAX_CHARS", "3000"))  # Polly hard limit is 3000 for plain text
URL_EXPIRY_SECONDS = int(os.getenv("URL_EXPIRY_SECONDS", "3600"))

AUDIO_BUCKET = os.environ["AUDIO_BUCKET"]

polly = boto3.client("polly")
s3 = boto3.client("s3")

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")


# -------- Helpers --------
def _json_response(code: int, payload: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
    }
    return {"statusCode": code, "headers": headers, "body": json.dumps(payload)}



def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw)
    try:
        return json.loads(raw)
    except Exception:
        raise ValueError("Invalid JSON body")


def _read_inputs(body: Dict[str, Any]) -> Tuple[str, str, str, bool]:
    text = (body.get("text") or "").strip()
    if not text:
        raise ValueError("Field 'text' is required")

    if len(text) > MAX_CHARS:
        raise ValueError(f"Text too long ({len(text)} chars). Limit is {MAX_CHARS}.")

    fmt = (body.get("format") or "mp3").strip().lower()
    if fmt not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS.keys())
        raise ValueError(f"'format' must be one of: {supported}")

    voice_id = (body.get("voiceId") or DEFAULT_VOICE).strip()
    use_ssml = bool(body.get("useSsml", False))

    return text, voice_id, fmt, use_ssml


def _synthesize(text: str, voice_id: str, fmt: str, use_ssml: bool) -> bytes:
    output_format = SUPPORTED_FORMATS[fmt][1]
    kwargs = {
        "VoiceId": voice_id,
        "OutputFormat": output_format,
    }
    if use_ssml:
        kwargs["TextType"] = "ssml"
        kwargs["Text"] = text
    else:
        kwargs["Text"] = text

    resp = polly.synthesize_speech(**kwargs)
    stream = resp.get("AudioStream")
    if not stream:
        raise RuntimeError("Polly returned no audio stream")
    return stream.read()


def _store_audio(fmt: str, data: bytes) -> Tuple[str, str, str]:
    ext = "mp3" if fmt == "mp3" else ("ogg" if fmt == "ogg_vorbis" else "pcm")
    key = f"audio/{uuid.uuid4()}.{ext}"
    content_type = SUPPORTED_FORMATS[fmt][0]
    s3.put_object(Bucket=AUDIO_BUCKET, Key=key, Body=data, ContentType=content_type)
    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": AUDIO_BUCKET, "Key": key},
        ExpiresIn=URL_EXPIRY_SECONDS,
    )
    return key, content_type, url


# -------- Handler --------
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    # Simple structured log (helps in CloudWatch)
    print(json.dumps({
        "message": "request_received",
        "requestId": getattr(context, "aws_request_id", None),
        "sourceIp": event.get("requestContext", {}).get("http", {}).get("sourceIp"),
        "route": event.get("rawPath"),
    }))

    try:
        body = _parse_body(event)
        text, voice_id, fmt, use_ssml = _read_inputs(body)
        audio = _synthesize(text, voice_id, fmt, use_ssml)
        key, content_type, url = _store_audio(fmt, audio)

        return _json_response(200, {
            "audioUrl": url,
            "bucket": AUDIO_BUCKET,
            "key": key,
            "voiceId": voice_id,
            "format": fmt,
            "contentType": content_type,
            "ssml": use_ssml
        })

    except ValueError as ve:
        return _json_response(400, {"error": str(ve)})
    except (BotoCoreError, ClientError) as aws_err:
        return _json_response(500, {"error": "AWS error", "detail": str(aws_err)})
    except Exception as e:
        return _json_response(500, {"error": "Unexpected error", "detail": str(e)})
