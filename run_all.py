from datetime import date
from step2_dataset import ORGANISATIONS, CERTIFICATES, PRODUCTS, CLAIMS
from step3_engine import ValidationEngine
from step4_report import print_console

CHECK_DATE = date(2026, 8, 23)

print(f"Certificates loaded: {len(CERTIFICATES)}")
engine = ValidationEngine(ORGANISATIONS, CERTIFICATES, PRODUCTS)
results = [engine.verify(claim, CHECK_DATE) for claim in CLAIMS]

print(f"\nClaim verification -- check date {CHECK_DATE.isoformat()}")
print_console(results)
