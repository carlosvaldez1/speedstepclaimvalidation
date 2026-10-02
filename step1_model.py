"""
STEP 1 -- DATA MODEL (Option D: full component structure)
============================================================
Same building blocks as the original PoC: certificates carry a structured
scope; products are broken into components (BOM); each component has its
own supplier; a claim is only VERIFIED if every component is covered
(the "component principle").

What's new for Option D: certificates are no longer hand-typed. See
extract.py -- Certificate objects are built automatically by reading a
real PDF and asking a local LLM to return the structured fields.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class SupplyChainRole(str, Enum):
    BRAND = "Brand"
    MANUFACTURER = "Manufacturer"
    ACCESSORY_SUPPLIER = "Accessory supplier"


@dataclass
class Organisation:
    org_id: str
    name: str
    country: str
    roles: list[SupplyChainRole]


class CertificateType(str, Enum):
    STANDARD_100 = "OEKO-TEX STANDARD 100"
    ORGANIC_COTTON = "OEKO-TEX ORGANIC COTTON"
    STEP = "OEKO-TEX STeP"


class ProductClass(int, Enum):
    I = 1
    II = 2
    III = 3
    IV = 4

    def covers(self, required: "ProductClass") -> bool:
        return self.value <= required.value


@dataclass
class CertificateScope:
    article_types: list[str]
    materials: list[str]
    product_stage: Optional[str] = None
    accessories_included: bool = False
    components_precertified: bool = False
    organic_content_pct: Optional[float] = None
    raw_text: str = ""


@dataclass
class Certificate:
    cert_id: str
    cert_type: CertificateType
    holder_org_id: str
    institute: str
    valid_until: date
    product_class: Optional[ProductClass]
    scope: CertificateScope
    source_document: str = ""
    extraction_confidence: str = "unknown"   # "high"/"medium"/"low" -- set by extract.py

    def is_valid_on(self, on: date) -> bool:
        return on <= self.valid_until


@dataclass
class ProductComponent:
    component_id: str
    position: str
    materials: list[str]
    supplier_org_id: Optional[str]   # None = data gap, no certificate can be found


@dataclass
class Product:
    product_id: str
    name: str
    article_no: str
    manufacturer_org_id: str
    required_product_class: ProductClass
    components: list[ProductComponent]


class ClaimType(str, Enum):
    HARMFUL_SUBSTANCES_TESTED = "tested for harmful substances"
    ORGANIC_CONTENT = "contains organic cotton"
    SUSTAINABLE_PRODUCTION_FACILITY = "produced in an environmentally responsible facility"
    GENERIC_SUSTAINABILITY = "sustainable"


CLAIM_EVIDENCE_MAP: dict[ClaimType, list[CertificateType]] = {
    ClaimType.HARMFUL_SUBSTANCES_TESTED: [CertificateType.STANDARD_100, CertificateType.ORGANIC_COTTON],
    ClaimType.ORGANIC_CONTENT: [CertificateType.ORGANIC_COTTON],
    ClaimType.SUSTAINABLE_PRODUCTION_FACILITY: [CertificateType.STEP],
    ClaimType.GENERIC_SUSTAINABILITY: [],
}

PRODUCT_LEVEL_CLAIMS = {ClaimType.HARMFUL_SUBSTANCES_TESTED, ClaimType.ORGANIC_CONTENT,
                        ClaimType.GENERIC_SUSTAINABILITY}


@dataclass
class Claim:
    claim_id: str
    product_id: str
    claim_type: ClaimType
    text_as_advertised: str


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    EXPIRED = "EXPIRED"
    UNSUPPORTED = "UNSUPPORTED"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"


@dataclass
class Finding:
    subject: str
    certificate_id: Optional[str]
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    explanation: str = ""


@dataclass
class ClaimVerification:
    claim: Claim
    verdict: Verdict
    check_date: date
    findings: list[Finding]
    summary: str
