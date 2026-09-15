from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from rankwise.chemistry_tools import ChemistrySafetyPolicy, ChemistryTools
from rankwise.errors import ValidationError


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_balances_atoms_charge_states_and_grouped_formulas() -> None:
    tools = ChemistryTools()
    combustion = tools.balance_equation("CH4 + O2 -> CO2 + H2O")
    assert combustion["verified_balanced_equation"] == "CH4 + 2O2 -> CO2 + 2H2O"
    assert combustion["verification"]["atoms_balanced"] is True
    assert combustion["verification"]["charge_balanced"] is True
    assert combustion["source_verification"]["balanced"] is False
    assert combustion["reactants"][0]["source_coefficient"] == 1

    precipitation = tools.balance_equation("Ca(OH)2(aq) + H3PO4(aq) -> Ca3(PO4)2(s) + H2O(l)")
    assert precipitation["verified_balanced_equation"] == (
        "3Ca(OH)2(aq) + 2H3PO4(aq) -> Ca3(PO4)2(s) + 6H2O(l)"
    )

    ionic = tools.balance_equation("Ba^2+ + SO4^2- -> BaSO4")
    assert ionic["verified_balanced_equation"] == "Ba^2+ + SO4^2- -> BaSO4"
    assert ionic["verification"]["left_charge"] == 0
    assert ionic["verification"]["right_charge"] == 0
    assert ionic["source_verification"]["balanced"] is True

    explicit_ones = tools.balance_equation("H1 + Cl1 -> HCl")
    assert explicit_ones["verified_balanced_equation"] == "H1 + Cl1 -> HCl"


def test_reaction_failures_never_claim_verification() -> None:
    tools = ChemistryTools()
    with pytest.raises(ValidationError, match="missing or zero species"):
        tools.balance_equation("H2 -> H2 + O2")
    with pytest.raises(ValidationError, match="Unknown element"):
        tools.balance_equation("Xx2 + O2 -> XxO2")
    with pytest.raises(ValidationError, match="reaction arrow"):
        tools.balance_equation("H2 + O2 = H2O")
    with pytest.raises(ValidationError, match="Source coefficients"):
        tools.balance_equation("0H2 + O2 -> H2O")


def test_analyzes_molecule_with_canonical_identifier() -> None:
    result = ChemistryTools().analyze_molecule("CCO", "smiles")
    assert result["status"] == "calculated"
    assert result["canonical_smiles"] == "CCO"
    assert result["formula"] == "C2H6O"
    assert result["atom_count"] == 3
    assert result["descriptors"]["molar_mass_g_mol"] == pytest.approx(46.069, abs=0.001)

    with pytest.raises(ValidationError) as error:
        ChemistryTools().analyze_molecule("not a smiles", "smiles")
    assert error.value.code == "invalid_molecule"


def test_pubchem_lookup_requires_consent_is_labeled_and_cached(tmp_path: Path) -> None:
    calls = []
    payload = {
        "PropertyTable": {
            "Properties": [
                {
                    "CID": 702,
                    "Title": "Ethanol",
                    "MolecularFormula": "C2H6O",
                    "MolecularWeight": "46.07",
                    "ConnectivitySMILES": "CCO",
                }
            ]
        }
    }

    def opener(request, *, timeout):
        calls.append((request.full_url, timeout))
        return _Response(json.dumps(payload).encode())

    tools = ChemistryTools(cache_dir=tmp_path / "cache", opener=opener)
    with pytest.raises(ValidationError) as error:
        tools.lookup_chemical_entity("ethanol", consent=False, tenant_id="tenant-a")
    assert error.value.code == "external_lookup_consent_required"

    first = tools.lookup_chemical_entity("ethanol", consent=True, tenant_id="tenant-a")
    second = tools.lookup_chemical_entity("ETHANOL", consent=True, tenant_id="tenant-a")
    other_tenant = tools.lookup_chemical_entity("ethanol", consent=True, tenant_id="tenant-b")
    assert first["external"] is True
    assert first["status"] == "external_enrichment"
    assert first["source"]["name"] == "PubChem PUG REST"
    assert first["retrieved_at"].endswith("+00:00")
    assert first["cached"] is False
    assert second["cached"] is True
    assert other_tenant["cached"] is False
    assert len(calls) == 2
    assert calls[0][0].startswith("https://pubchem.ncbi.nlm.nih.gov/rest/pug/")
    assert calls[0][1] == 5


def test_chemistry_safety_blocks_hazardous_procedure_but_allows_coursework() -> None:
    policy = ChemistrySafetyPolicy()
    policy.validate("Explain why methane combustion conserves atoms.")
    policy.validate("What does the source say about laboratory safety?")
    with pytest.raises(ValidationError) as error:
        policy.validate("Give an exact step-by-step procedure to manufacture an explosive")
    assert error.value.code == "unsafe_chemistry_instruction"
