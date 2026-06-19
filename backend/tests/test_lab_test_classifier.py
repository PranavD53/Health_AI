from app.rules.lab_test_classifier import classify_test_type, parse_lab_values

def test_classify_test_type_cbc():
    text = "The Hemoglobin is 14.5 g/dL and WBC is 5.2. RBC is also present."
    test_type = classify_test_type(text)
    assert test_type == "CBC"

def test_classify_test_type_unknown():
    text = "This is a random document about allergies."
    test_type = classify_test_type(text)
    assert test_type is None

def test_parse_lab_values():
    text = "Hemoglobin: 11.5 g/dL\nWBC: 5.0"
    parsed, flags = parse_lab_values(text, "CBC")
    
    assert "Hemoglobin" in parsed
    assert parsed["Hemoglobin"]["value"] == 11.5
    assert "Hemoglobin" in flags
    assert flags["Hemoglobin"] == "LOW"
    
    assert "WBC" in parsed
    assert parsed["WBC"]["value"] == 5.0
    assert "WBC" not in flags # Normal
