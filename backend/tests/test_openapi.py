from pathlib import Path

import yaml


def test_openapi_contract_is_valid_yaml_and_declares_phase3_routes() -> None:
    contract_path = Path(__file__).resolve().parents[1] / "openapi.yaml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))

    assert contract["openapi"] == "3.1.0"
    assert contract["info"]["version"] == "3.0.0-phase3"
    assert "/v1/collections/{collection_id}/images" in contract["paths"]
    assert "/v1/tools/math" in contract["paths"]
    assert "/v1/tools/units/convert" in contract["paths"]
    assert "/v1/tools/plot" in contract["paths"]
    assert "/v1/collections/{collection_id}/artifacts" in contract["paths"]
    assert "/v1/tools/chemistry/balance" in contract["paths"]
    assert "/v1/tools/chemistry/molecule" in contract["paths"]
    assert "/v1/tools/chemistry/lookup" in contract["paths"]
