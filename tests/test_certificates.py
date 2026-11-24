import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.certificates import NOT_API_RX


def test_intermediates_are_not_api_suppliers():
    for s in ["SEMAGLUTIDE SIDE CHAIN", "EMPAGLIFLOZIN ADVANCED INTERMIDIATE (EP2)", "APIXABAN INTERMEDIATE",
              "METFORMIN HYDROCHLORIDE TABLETS USP", "ATORVASTATIN KEY STARTING MATERIAL", "OMEPRAZOLE PELLETS 8.5%"]:
        assert NOT_API_RX.search(s), s


def test_real_api_subjects_pass():
    for s in ["METFORMIN HYDROCHLORIDE USP (PROCESS-II)", "SEMAGLUTIDE, NON-STERILE DRUG SUBSTANCE",
              "EMPAGLIFLOZIN (AMORPHOUS)", "SACUBITRIL SODIUM"]:
        assert not NOT_API_RX.search(s), s
