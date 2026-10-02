OEKO-TEX Claim Verification

Checks if a sustainability claim on a product ("tested for harmful substances", "a sustainable choice") is actually backed by a real certificate — not just that a certificate exists, but that it actually covers the right materials, the right product, and hasn't expired.

Built for the EU's new green claims rules (EmpCo), which from September 2026 put the burden of proof on companies making these claims.

What it does
Reads a certificate PDF and pulls out the key fields (ID, materials, dates, scope) using a local AI model — no manual typing
Breaks a product down into its parts — fabric, zipper, labels — since different parts often come from different suppliers
Checks each part against its own supplier's certificate
Gives a pass/fail per claim with a plain explanation, not just yes or no
Why

A certificate existing doesn't mean it backs a specific claim. Common issues this catches:

A certificate for one product type being used to justify a claim about something else
A safety certificate being stretched to cover a general "sustainable" claim
Expired certificates
Materials that don't actually match what's certified
Setup
bash
pip install pdfplumber transformers torch --break-system-packages

Add certificate PDFs to a certificates/ folder, update the file paths in step2_dataset.py, then run:

bash
python run_all.py

First run downloads the model — give it a minute.

Files
step1_model.py — the data structures
extract.py — reads PDFs, pulls out structured data
step2_dataset.py — certificate + product data for this test case
step3_engine.py — the actual checking logic
step4_report.py — prints the results
run_all.py — runs everything

What's not done yet
No real link between products and suppliers — typed in by hand for now, no PLM data available
One product at a time, not built for checking a whole catalog yet
Using a small AI model for speed, so extraction isn't always perfect — worth double-checking low-confidence results
Checks general claim types for now, not exact wording from real product pages
Status

Working end to end, tested on real OEKO-TEX certificates.
