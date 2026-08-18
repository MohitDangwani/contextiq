"""Tests for the grounding gate (app.agent.grounding.verify_support) --
the code-enforced check that evidence existing does NOT automatically
mean a question is answerable. Unlike test_agent.py, these construct
evidence/trace directly rather than running the full agent loop: faster,
and lets each scenario (relevant / irrelevant / partial / targeted-
not-found-vs-broad-hit) be tested in isolation and deterministically,
without depending on which tools the agent happens to pick on a given
run. Still a real LLM call (verify_support's classification), no DB.
"""
from app.agent.grounding import verify_support
from app.agent.state import EvidenceItem, ToolInvocation


def _evidence(asset_id: str, detail: str, source_type: str = "asset") -> EvidenceItem:
    return EvidenceItem(source_type=source_type, title=asset_id, asset_id=asset_id, detail=detail,
                         citation=f"{asset_id} (catalog metadata)")


def test_relevant_evidence_is_supported():
    evidence = [_evidence("orders", "orders (Orders): owner=Sales Engineering, domain=sales")]
    verdict = verify_support("Who owns the orders dataset?", evidence, trace=[])
    assert verdict.status == "supported"


def test_irrelevant_evidence_is_not_supported():
    """Class 12: evidence exists, is real, and is about a real dataset --
    just not the one asked about. Must not be accepted as grounding."""
    evidence = [_evidence("payments", "payments (Payments): owner=Finance Analytics, domain=finance, "
                                       "pii_status=contains_pii, quality_score=72.0")]
    verdict = verify_support("What is the owner of the employee_attrition dataset?", evidence, trace=[])
    assert verdict.status == "not_supported"


def test_right_entity_wrong_attribute_is_not_supported():
    """The harder version of class 12: evidence isn't just about a
    different dataset -- it's about the SAME dataset the question names,
    but a different attribute entirely (PII/quality facts when the
    question asks about a backup/disaster-recovery policy). Same-entity
    evidence is not automatically on-topic."""
    evidence = [
        _evidence("payments", "payments (Payments): a finance-domain table that contains PII, "
                               "owned by Finance Analytics, quality_score=72.0"),
        _evidence("revenue_model", "revenue_model: a finance-domain model that does not contain "
                                    "PII, owned by Finance Analytics, quality_score=93.0"),
    ]
    verdict = verify_support(
        "What is ContextIQ's disaster recovery and backup retention policy for the payments database?",
        evidence, trace=[],
    )
    assert verdict.status == "not_supported"


def test_targeted_not_found_not_overridden_by_unrelated_broad_hit():
    """Class 13 / Invariant 4: a targeted lookup for the actual entity
    came back empty (evidence_count=0, recorded in trace); a separate,
    broader search happened to return something real but unrelated. The
    unrelated hit must not overturn the targeted "not found"."""
    evidence = [_evidence("payments", "payments (Payments): domain=finance, owner=Finance Analytics")]
    trace = [
        ToolInvocation(
            tool="get_owner", input={"asset_id": "employee_attrition"},
            output_summary="No dataset with id 'employee_attrition' exists in the ContextIQ catalog.",
            timestamp="2026-01-01T00:00:00Z", evidence_count=0,
        ),
        ToolInvocation(
            tool="search_assets", input={"domain": "finance"},
            output_summary="Matching datasets:\n- payments (Payments): domain=finance, owner=Finance Analytics",
            timestamp="2026-01-01T00:00:01Z", evidence_count=1,
        ),
    ]
    verdict = verify_support("What is the owner of the employee_attrition dataset?", evidence, trace)
    assert verdict.status == "not_supported"


def test_partial_evidence_is_classified_partial():
    """Class 14: one sub-question answered, the other has no evidence at all."""
    evidence = [_evidence("orders", "orders is owned by Sales Engineering")]
    verdict = verify_support(
        "What is the owner of the orders dataset, and what is its GDPR data retention period?",
        evidence, trace=[],
    )
    assert verdict.status == "partial"


def test_fully_answered_multi_part_question_is_supported():
    """Symmetric check: when evidence genuinely covers every part asked,
    the verdict should be supported, not partial -- confirms the gate
    isn't just defaulting to partial/cautious for any multi-part question."""
    evidence = [
        _evidence("customers", "customers (Customers): pii_status=contains_pii, owner=Sales Engineering"),
        _evidence("orders", "orders (Orders): pii_status=contains_pii, owner=Sales Engineering"),
    ]
    verdict = verify_support("Which datasets contain PII and are owned by Sales Engineering?", evidence, trace=[])
    assert verdict.status == "supported"
