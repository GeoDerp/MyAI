from myai._research_agent import FinalAnswer, ResearchDependencies, ResearchSource, generate_provenance


def test_generate_provenance_basic():
    deps = ResearchDependencies()
    # create a fake source with fingerprint and meta
    src = ResearchSource(
        title="Important Paper on Testing",
        url="https://example.org/paper",
        confidence=0.9,
        fingerprint="fp-abc123",
        meta={"DOI": "10.1000/testdoi"},
    )
    deps.sources_collected = [src]

    final = FinalAnswer(
        answer="This system uses results from Important Paper on Testing to reach the conclusion.",
        reasoning="As shown in Important Paper on Testing (10.1000/testdoi), the effect is significant.",
    )

    prov = generate_provenance(final, deps)
    assert "fp-abc123" in prov
    entry = prov["fp-abc123"]
    # should include both sentences that mention title and DOI
    assert any("Important Paper on Testing" in c for c in entry["claims"]) or any("10.1000/testdoi" in c for c in entry["claims"])

    # ensure metadata carried through
    assert entry["title"] == "Important Paper on Testing"
    assert entry["url"] == "https://example.org/paper"

    # now test the formatted report and apply helper
    from myai._research_agent import format_provenance_report, apply_provenance_to_final

    report = format_provenance_report(final, deps)
    assert "by_fingerprint" in report and "by_claim_id" in report
    # there should be at least one claim id referencing our fingerprint
    found = False
    for cid, info in report["by_claim_id"].items():
        if "fp-abc123" in info["fingerprints"]:
            found = True
            assert info["claim"].startswith("This system uses results") or "Important Paper on Testing" in info["claim"] or "10.1000/testdoi" in info["claim"]
    assert found

    # apply to final answer
    apply_provenance_to_final(final, deps)
    assert final.provenance is not None
    assert "by_fingerprint" in final.provenance
