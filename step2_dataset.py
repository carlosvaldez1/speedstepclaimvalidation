"""
STEP 2 -- DATASET
=================
CERTIFICATES are no longer hand-typed -- extract_certificate() reads real
PDFs and asks a local LLM to return the structured fields (see extract.py).

The BOM (which supplier made which part of the product) is still typed in
by hand below -- there's no PLM/SCM system feeding that in automatically
yet. That's the data gap flagged throughout this project: without it,
components with supplier_org_id=None can't be checked against any
certificate at all.

TO USE WITH YOUR OWN PDFs:
  1. Put your certificate PDF files in a local folder (e.g. ./certificates/)
  2. Update the CERT_PDF_PATHS dict below with the real file paths
  3. Make sure Ollama is running (ollama pull llama3.1, then it runs automatically)
  4. Run run_all.py -- certificates are extracted fresh each run
"""

from step1_model import *
from extract import extract_certificate, ExtractionError

ORGANISATIONS = {o.org_id: o for o in [
    Organisation("ORG-SEGERS", "Segers Fabriker AB", "SE", [SupplyChainRole.MANUFACTURER]),
    Organisation("ORG-YIHUI", "Zhejiang Yihui Accessories Technology Co., Ltd.", "CN",
                 [SupplyChainRole.ACCESSORY_SUPPLIER]),
]}

# Map each organisation to the PDF file of the certificate it holds.
# Paths are relative to files/ (where run_all.py actually lives).
CERT_PDF_PATHS = {
    "ORG-SEGERS": "./certificates/certificate (9) (1).pdf",
    "ORG-YIHUI": "./certificates/certificate (11) (1).pdf",
}


def load_certificates() -> dict[str, Certificate]:
    """Extract every certificate from its PDF. Prints a clear error and skips
    (rather than crashing the whole run) if one specific PDF can't be read --
    so one bad file doesn't block testing the rest of the pipeline."""
    certificates = {}
    for org_id, pdf_path in CERT_PDF_PATHS.items():
        try:
            cert = extract_certificate(pdf_path, holder_org_id=org_id)
            certificates[cert.cert_id] = cert
            print(f"  Extracted {cert.cert_id} from {pdf_path} (confidence: {cert.extraction_confidence})")
        except ExtractionError as e:
            print(f"  [SKIPPED] {pdf_path}: {e}")
        except FileNotFoundError:
            print(f"  [SKIPPED] {pdf_path}: file not found -- update CERT_PDF_PATHS with a real path.")
    return certificates


CERTIFICATES = load_certificates()

# ---------------------------------------------------------------------------
# BOM -- manually entered. This is the piece that would normally come from
# a PLM/SCM system; here it's typed in by hand for one test product.
# ---------------------------------------------------------------------------

PRODUCTS = {p.product_id: p for p in [
    Product(
        product_id="P-225",
        name="Work jacket 'Attention'",
        article_no="225_10320",
        manufacturer_org_id="ORG-SEGERS",
        required_product_class=ProductClass.II,
        components=[
            ProductComponent("C-01", "Fabric", ["CO", "PES"], supplier_org_id="ORG-SEGERS"),
            ProductComponent("C-02", "Zipper", ["brass", "PES"], supplier_org_id="ORG-YIHUI"),
            ProductComponent("C-03", "Velcro", ["PA"], supplier_org_id=None),  # unknown supplier -- data gap
        ],
    ),
]}

CLAIMS = [
    Claim("CL-1", "P-225", ClaimType.HARMFUL_SUBSTANCES_TESTED,
          "Tested for harmful substances according to OEKO-TEX STANDARD 100"),
    Claim("CL-2", "P-225", ClaimType.GENERIC_SUSTAINABILITY,
          "A sustainable choice"),
]
