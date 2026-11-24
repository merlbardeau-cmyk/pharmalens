import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.gsrs import is_salt_name


def test_salt_names():
    assert is_salt_name("OMEPRAZOLE MAGNESIUM", "Omeprazole")
    assert is_salt_name("Atorvastatin calcium trihydrate", "Atorvastatin")
    assert not is_salt_name("ESOMEPRAZOLE MAGNESIUM", "Omeprazole")
    assert not is_salt_name("AMLODIPINE AND VALSARTAN", "Amlodipine")
    assert not is_salt_name("Omeprazole", "Omeprazole")
