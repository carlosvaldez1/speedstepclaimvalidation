"""
STEP 3 -- VALIDATION ENGINE (component principle restored)
=============================================================
For each claim: check EVERY component of the product. A product-level
claim only passes if all components are covered by a valid, in-scope
certificate held by that component's own supplier.
"""

from __future__ import annotations
from datetime import date
from typing import Optional
from step1_model import *


class ValidationEngine:
    def __init__(self, organisations: dict, certificates: dict, products: dict):
        self.organisations = organisations
        self.certificates = certificates
        self.products = products

    def certificates_for_org(self, org_id: Optional[str]) -> list[Certificate]:
        if org_id is None:
            return []
        return [c for c in self.certificates.values() if c.holder_org_id == org_id]

    @staticmethod
    def _materials_covered(component: ProductComponent, cert: Certificate) -> bool:
        cert_mats = {m.lower() for m in cert.scope.materials}
        return all(m.lower() in cert_mats for m in component.materials)

    def _check_component(self, product: Product, component: ProductComponent,
                         claim: Claim, check_date: date) -> Finding:
        eligible_types = CLAIM_EVIDENCE_MAP[claim.claim_type]
        certs = [c for c in self.certificates_for_org(component.supplier_org_id)
                 if c.cert_type in eligible_types]

        # Fallback: manufacturer's own certificate can cover a component if it
        # explicitly claims to use exclusively pre-certified components.
        if not certs:
            for c in self.certificates_for_org(product.manufacturer_org_id):
                if (c.cert_type in eligible_types and c.scope.components_precertified):
                    certs.append(c)

        if not certs:
            reason = ("no certificate of an eligible type found for this supplier"
                      if component.supplier_org_id else
                      "supplier unknown -- no certificate can be looked up (data gap)")
            return Finding(subject=f"{component.position}", certificate_id=None,
                          passed=False, explanation=reason)

        best: Optional[Finding] = None
        for cert in certs:
            checks = {
                "validity": cert.is_valid_on(check_date),
                "product_class": (cert.product_class is not None and
                                  cert.product_class.covers(product.required_product_class)),
                "materials_in_scope": self._materials_covered(component, cert),
            }
            passed = all(checks.values())
            if passed:
                return Finding(subject=component.position, certificate_id=cert.cert_id,
                              passed=True, checks=checks,
                              explanation=f"Covered by {cert.cert_id}, valid until {cert.valid_until.isoformat()}.")

            reasons = []
            if not checks["validity"]:
                reasons.append(f"{cert.cert_id} expired {cert.valid_until.isoformat()}")
            if not checks["product_class"]:
                reasons.append("certified class doesn't cover this product's use")
            if not checks["materials_in_scope"]:
                missing = [m for m in component.materials
                           if m.lower() not in {x.lower() for x in cert.scope.materials}]
                reasons.append(f"materials not in scope: {', '.join(missing)}")

            finding = Finding(subject=component.position, certificate_id=cert.cert_id,
                             passed=False, checks=checks, explanation="; ".join(reasons))
            if best is None or sum(checks.values()) > sum(best.checks.values()):
                best = finding
        return best

    def verify(self, claim: Claim, check_date: date) -> ClaimVerification:
        product = self.products[claim.product_id]

        if not CLAIM_EVIDENCE_MAP[claim.claim_type]:
            return ClaimVerification(
                claim=claim, verdict=Verdict.UNSUPPORTED, check_date=check_date, findings=[],
                summary=f"Generic claim ('{claim.text_as_advertised}') -- no certificate type can substantiate it.",
            )

        findings = [self._check_component(product, comp, claim, check_date)
                    for comp in product.components]
        n_pass = sum(f.passed for f in findings)
        n = len(findings)

        if n_pass == n:
            verdict = Verdict.VERIFIED
            summary = f"All {n} components covered by valid certificates."
        elif n_pass == 0:
            verdict = Verdict.MISSING_EVIDENCE
            summary = "No component is covered by eligible evidence."
        else:
            verdict = Verdict.PARTIAL
            summary = f"{n_pass} of {n} components covered -- claim NOT substantiated (component principle)."

        return ClaimVerification(claim=claim, verdict=verdict, check_date=check_date,
                                 findings=findings, summary=summary)
