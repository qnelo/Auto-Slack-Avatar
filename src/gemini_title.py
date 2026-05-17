"""Satirical Slack profile ``title`` text via Gemini (text-only).

Uses the same Gemini API key as image generation but a configurable
text-capable ``GEMINI_TEXT_MODEL``.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from src.gemini_image import (
    _free_tier_quota_unavailable,
    _retry_seconds_from_client_error,
)

_logger = logging.getLogger(__name__)

_MAX_LINE_LEN = 100

_LINE_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"[\-*•]|"
    r"\[[0-9]+\]|"
    r"[0-9]+[\).\]]"
    r")\s*",
)


# User-provided persona and style constraints (Spanish)
_CORPORATE_SATIRE_SYSTEM = """\
Actúa como un consultor corporativo satírico y experto en parodiar el "corporate-speak" y los títulos pretenciosos de LinkedIn.

Tu objetivo es generar una única opción de título/rol profesional ficticio e hiper-inflado para poner en el Título del perfil de Slack. Debe describir lo que la persona supuestamente "realiza" en la empresa.

Directrices de Estilo:
Formato de Rol: Debe sonar como la descripción de un puesto o la misión de una persona en la organización (ej. Arquitecto de..., Evangelista de..., Facilitador de..., Gestor de...).

Tono: Sarcástico, falsamente profundo y corporativo. Debe sonar increíblemente complejo y motivador, pero ser completamente vacío en la práctica.

Vocabulario: Utiliza términos rebuscados, rimbombantes y tecnicismos de negocios (ej. sinergia, disrupción, holístico, ontológico, vectores de crecimiento, resiliencia sistémica, convergencia cuántica, flujos de valor).

Cantidad: Entrega estrictamente una (1) sola opción, directa y lista para usar. Sin introducciones, explicaciones ni listas alternativas.

Ejemplos de inspiración:
"Arquitecto de convergencia holística y catalizador de disrupciones sistémicas."

"Evangelista de resiliencia cuántica encargado de la optimización de vectores ontológicos."
"""


_FORMAT_INSTRUCTION = """\
Respond in plain text only. Output strictly:
- A single line: one standalone phrase only (no numbering, bullets, quotes,
  preamble, or closing text).
- At most 100 characters including spaces; output nothing else.
"""


def _strip_line_prefix(raw: str) -> str:
    s = raw.strip()
    while True:
        nxt = _LINE_PREFIX_RE.sub("", s, count=1)
        if nxt == s:
            break
        s = nxt.strip()
    return s.strip().strip("\"'")


def parse_single_title(text: str) -> str:
    """Return the first usable non-empty line, trimmed to length cap."""
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = _strip_line_prefix(raw)
        if not line:
            continue
        if len(line) > _MAX_LINE_LEN:
            return line[:_MAX_LINE_LEN]
        return line
    msg = "Gemini text output had no usable title line"
    raise RuntimeError(msg)


def _call_gemini_text(*, api_key: str, model: str, prompt: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=[types.Part.from_text(text=prompt)],
    )
    blob: Any = getattr(response, "text", "") or ""
    if not blob.strip():
        msg = "Gemini text model returned no text"
        raise RuntimeError(msg)
    return str(blob)


def generate_slack_profile_title_once(
    *,
    api_key: str,
    model: str,
) -> str:
    """One Gemini call plus parse; raises if no usable line."""
    prompt = (
        _CORPORATE_SATIRE_SYSTEM.strip() + "\n\n" + _FORMAT_INSTRUCTION.strip()
    )
    raw = _call_gemini_text(api_key=api_key, model=model, prompt=prompt)
    return parse_single_title(raw)


def generate_slack_profile_title(
    *,
    api_key: str,
    model: str,
    max_429_attempts: int = 4,
) -> str:
    """Retries 429 similarly to image generation."""
    last: ClientError | None = None
    for attempt in range(max_429_attempts):
        try:
            return generate_slack_profile_title_once(
                api_key=api_key,
                model=model,
            )
        except ClientError as exc:
            last = exc
            if exc.code != 429:
                raise
            if _free_tier_quota_unavailable(exc):
                _logger.warning(
                    "Gemini title: free-tier quota exhausted; not retrying.",
                )
                raise
            delay = _retry_seconds_from_client_error(exc)
            if attempt + 1 >= max_429_attempts:
                raise
            _logger.warning(
                "Gemini title rate limited (429), retry %s/%s after %.1fs",
                attempt + 1,
                max_429_attempts,
                delay,
            )
            time.sleep(delay)
    assert last is not None
    raise last
