BADGE = {
    "VERIFIED": "[PASS]", "PARTIAL": "[PARTIAL]", "EXPIRED": "[EXPIRED]",
    "UNSUPPORTED": "[UNSUPPORTED]", "MISSING_EVIDENCE": "[MISSING EVIDENCE]",
}

def print_console(results):
    for r in results:
        print(f"\n{BADGE[r.verdict.value]} {r.claim.claim_id}: \"{r.claim.text_as_advertised}\"")
        print(f"   {r.summary}")
        for f in r.findings:
            mark = "  ok " if f.passed else " FAIL"
            print(f"   {mark} | {f.subject}: {f.explanation}")
