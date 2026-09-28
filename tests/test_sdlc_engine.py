from src.sdlc_engine import (aggregate, build_workflow, evaluate, factor_names, load_sdlc, recommend,
                             suitability, workflow_markdown, workflow_mermaid)

REGULATED = {  # stable, safety-critical, heavily regulated, legacy-bound
    "requirement_instability": 2, "regulatory_criticality": 5, "security_risk": 5, "project_complexity": 3,
    "system_size": 4, "legacy_dependence": 4, "change_frequency": 2, "continuous_delivery_need": 2,
    "stakeholder_availability": 2, "documentation_rigour": 5, "schedule_budget_rigidity": 5,
    "formal_verification_need": 5, "failure_consequence": 5,
}
CONSUMER = {  # volatile, low-risk, continuously delivered
    "requirement_instability": 3, "regulatory_criticality": 2, "security_risk": 4, "project_complexity": 2,
    "system_size": 1, "legacy_dependence": 2, "change_frequency": 5, "continuous_delivery_need": 5,
    "stakeholder_availability": 5, "documentation_rigour": 2, "schedule_budget_rigidity": 2,
    "formal_verification_need": 1, "failure_consequence": 2,
}


def test_conditions():
    s = {"a_factor": 4, "b_factor": 2}
    assert evaluate("a_factor >= 4", s)
    assert not evaluate("b_factor >= 4", s)
    assert evaluate({"any": ["b_factor >= 4", "a_factor >= 4"]}, s)
    assert not evaluate({"all": ["b_factor >= 4", "a_factor >= 4"]}, s)
    assert not evaluate("missing >= 1", s)


def test_ranking_is_percentages_best_first():
    ranking = suitability(REGULATED)
    pcts = [r["pct"] for r in ranking]
    assert pcts == sorted(pcts, reverse=True)
    assert all(0 <= p <= 100 for p in pcts)
    assert len(ranking) == len(load_sdlc()["profiles"])


def test_regulated_project_prefers_plan_driven_over_agile():
    rec = recommend(REGULATED)
    order = [r["model"] for r in rec["ranking"]]
    assert rec["top"] in {"V-Model", "Waterfall"}
    assert order.index("Agile") > order.index("V-Model")
    assert "R-V" in {r["id"] for r in rec["fired_rules"]}


def test_consumer_project_prefers_adaptive_models():
    rec = recommend(CONSUMER)
    assert rec["top"] in {"Agile", "DevSecOps"}
    fired = {r["id"] for r in rec["fired_rules"]}
    assert {"R-AG", "R-DSO"} <= fired


def test_caution_when_adaptive_model_tops_a_regulated_project():
    scores = dict(CONSUMER, regulatory_criticality=5, failure_consequence=5)
    rec = recommend(scores)
    if rec["top"] in {"Agile", "DevSecOps"}:
        assert rec["cautions"] and rec["escalate"]


def test_aggregate_takes_the_median():
    agg = aggregate([{"change_frequency": 1}, {"change_frequency": 3}, {"change_frequency": 5}])
    assert agg == {"change_frequency": 3.0}


def test_workflow_overlays_and_template_is_not_mutated():
    before = [list(p["activities"]) for p in load_sdlc()["workflows"]["V-Model"]]
    phases = build_workflow("V-Model", {"D04", "D06"}, safety_critical=True, security_risk=5)
    after = [list(p["activities"]) for p in load_sdlc()["workflows"]["V-Model"]]
    assert before == after
    checkpoints = [c for p in phases for c in p["checkpoints"]]
    assert any("1311.300" in c for c in checkpoints)
    assert any("164.308" in c for c in checkpoints)
    assert any("Clinical" in a for p in phases for a in p["activities"])
    assert any(p["security"] for p in phases)
    gated = [p for p in phases if p["gate"]]
    assert gated and all(p.get("traceability") for p in gated)
    assert "| 1 |" in workflow_markdown("V-Model", phases)
    assert workflow_mermaid(phases).startswith("flowchart LR")


def test_every_factor_named_in_rules_exists():
    names = set(factor_names())
    for rule in load_sdlc()["rules"]:
        text = str(rule["when"])
        for token in __import__("re").findall(r"([a-z_]+) [<>=]", text):
            assert token in names, (rule["id"], token)
