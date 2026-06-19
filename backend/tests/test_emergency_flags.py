from app.rules.emergency_flags import detect_emergency

def test_detect_emergency_with_keywords():
    is_emergency, terms = detect_emergency("I have severe chest pain")
    assert is_emergency is True
    assert "chest pain" in terms

def test_detect_emergency_no_keywords():
    is_emergency, terms = detect_emergency("I have a mild headache")
    assert is_emergency is False
    assert len(terms) == 0

def test_detect_emergency_case_insensitive():
    is_emergency, terms = detect_emergency("StroKe symptoms")
    assert is_emergency is True
    assert "stroke" in [t.lower() for t in terms]
