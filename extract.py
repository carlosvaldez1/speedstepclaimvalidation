"""
EXTRACTION LAYER -- the actual new piece for Option D
=======================================================
Takes a real certificate PDF and returns a Certificate object, instead of
someone typing the scope fields in by hand.

Two steps:
  1. pdfplumber reads the raw text out of the PDF (no AI needed for this --
     it's a straightforward text-extraction library).
  2. That raw text is sent to a locally-run Hugging Face model (via the
     `transformers` library) with instructions to return the structured
     fields as JSON, which we then turn into a Certificate object using
     the same schema as step1_model.py.

Uses Hugging Face's `transformers` library -- the model downloads once
from the Hugging Face Hub and then runs fully locally, in this Python
process. No separate server, no Ollama. Swap MODEL_NAME below for any
other open model on the Hub.

Setup:
  pip install transformers torch pdfplumber --break-system-packages
  (first run downloads the model -- a few GB, one-time)

If extraction fails or the model returns something unusable, this raises
a clear error rather than silently producing a wrong/empty certificate --
a wrong certificate is worse than no certificate, since it would let a
bad claim pass silently.
"""

from __future__ import annotations
import json
import re
from datetime import date, datetime
from typing import Optional

import pdfplumber

from step1_model import Certificate, CertificateScope, CertificateType, ProductClass

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"  # ungated -- no HF login needed

_pipeline = None  # loaded once, lazily, on first use -- avoids a slow import/load
                  # if this module is imported but extraction is never called

EXTRACTION_SYSTEM_PROMPT = """You are a data-extraction assistant for OEKO-TEX \
certificates. You will be given the raw text of a certificate PDF. Extract the \
fields below EXACTLY as they appear -- never invent or guess a value you can't \
find in the text.

Fields to extract:
- cert_id: the certificate number (e.g. "2020OK0011", "23.HIN.77885")
- cert_type: one of "STANDARD_100", "ORGANIC_COTTON", or "STEP" -- based on the \
certificate's title (e.g. "OEKO-TEX STANDARD 100" -> "STANDARD_100")
- institute: the name of the certifying institute (right-hand address block, \
e.g. "AITEX", "Hohenstein Laboratories")
- valid_until: the expiry date, in YYYY-MM-DD format
- product_class: the roman numeral after "PRODUCT CLASS" (I, II, III, or IV), \
converted to a plain integer (I=1, II=2, III=3, IV=4). Use null if not stated.
- article_types: a list of the specific product/article types named in the SCOPE \
section (e.g. ["button", "buckle", "snap button"] or ["work wear"])
- materials: a list of material/fibre codes or names mentioned in the SCOPE \
(e.g. ["CO", "PES"] for cotton/polyester, or descriptive names like "brass" if no \
standard code is used)
- product_stage: "precursor" if the SCOPE describes a raw/intermediate material \
(yarn, fabric, comber noil) rather than a finished product, otherwise null
- organic_content_pct: a number 0-100 if an organic content percentage is stated, \
otherwise null
- confidence: "high" if every field above was clearly stated in the text, "medium" \
if some fields had to be inferred from ambiguous wording, "low" if the text was \
unclear, garbled, or scope information seemed to be missing/truncated

Respond ONLY with a JSON object, no other text, no markdown fences, in this exact shape:
{"cert_id": "...", "cert_type": "STANDARD_100", "institute": "...", "valid_until": "YYYY-MM-DD", \
"product_class": 2, "article_types": ["..."], "materials": ["..."], "product_stage": null, \
"organic_content_pct": null, "confidence": "high"}
"""


class ExtractionError(Exception):
    """Raised when a certificate PDF can't be read or the model's output can't be trusted."""


def read_pdf_text(pdf_path: str) -> str:
    """Pull the raw text out of a certificate PDF. No AI involved here."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    text = "\n\n".join(text_parts).strip()
    if not text:
        raise ExtractionError(
            f"No text could be read from {pdf_path} -- likely a scanned/image PDF."
        )
    return text


def _get_pipeline():
    """Load the Hugging Face model once, on first use, and reuse it after that
    (loading a model takes real time -- don't repeat it per certificate)."""
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline
        print(f"  Loading {MODEL_NAME} from Hugging Face (first run only)...")
        _pipeline = pipeline("text-generation", model=MODEL_NAME, device_map="auto")
    return _pipeline


def _call_model(raw_text: str) -> dict:
    pipe = _get_pipeline()
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": raw_text},
    ]
    try:
        output = pipe(messages, max_new_tokens=400, do_sample=False)
        content = output[0]["generated_text"][-1]["content"]
    except Exception as e:
        raise ExtractionError(f"Model call failed: {e}")

    cleaned = re.sub(r"```json|```", "", content).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise ExtractionError(
            f"Model did not return valid JSON. Raw output:\n{content[:500]}"
        )
    return data


def extract_certificate(pdf_path: str, holder_org_id: str) -> Certificate:
    """
    Read a certificate PDF and return a Certificate object.

    Raises ExtractionError if the PDF can't be read, Ollama can't be reached,
    the model's output isn't valid JSON, or a required field is missing --
    on purpose. A half-built Certificate is more dangerous than a loud failure,
    because it could silently pass a claim it shouldn't.
    """
    raw_text = read_pdf_text(pdf_path)
    data = _call_model(raw_text)

    required = ["cert_id", "cert_type", "institute", "valid_until"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        raise ExtractionError(f"Model output missing required fields: {missing}")

    try:
        cert_type = CertificateType[data["cert_type"]] if data["cert_type"] in CertificateType.__members__ \
            else CertificateType(f"OEKO-TEX {data['cert_type'].replace('_', ' ')}")
    except (KeyError, ValueError):
        raise ExtractionError(f"Unrecognised cert_type: {data.get('cert_type')}")

    try:
        valid_until = datetime.strptime(data["valid_until"], "%Y-%m-%d").date()
    except ValueError:
        raise ExtractionError(f"Could not parse valid_until date: {data.get('valid_until')}")

    product_class = None
    if data.get("product_class"):
        try:
            product_class = ProductClass(int(data["product_class"]))
        except (ValueError, TypeError):
            pass  # leave as None rather than guessing

    confidence = data.get("confidence", "unknown")
    if confidence == "low":
        print(f"  [!] Low-confidence extraction for {pdf_path} -- review manually before trusting this result.")

    return Certificate(
        cert_id=data["cert_id"],
        cert_type=cert_type,
        holder_org_id=holder_org_id,
        institute=data["institute"],
        valid_until=valid_until,
        product_class=product_class,
        scope=CertificateScope(
            article_types=data.get("article_types", []),
            materials=data.get("materials", []),
            product_stage=data.get("product_stage"),
            organic_content_pct=data.get("organic_content_pct"),
            raw_text=raw_text[:1000],  # keep an excerpt as an audit trail
        ),
        source_document=pdf_path,
        extraction_confidence=confidence,
    )
