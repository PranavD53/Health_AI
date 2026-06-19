from app.rules.triage_whitelist import is_self_care_eligible

def test_self_care_eligible_known_category():
    eligible, text = is_self_care_eligible("cold_flu")
    assert eligible is True
    assert "Rest" in text

def test_self_care_not_eligible_unknown_category():
    eligible, text = is_self_care_eligible("unknown_crazy_disease")
    assert eligible is False
    assert "consult a doctor" in text.lower()
