"""Bounded chemistry verification, molecule analysis, and opt-in enrichment."""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import reduce
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .errors import ConfigurationError, ValidationError

ARROWS = ("<=>", "⇌", "→", "->")
STATE_PATTERN = re.compile(r"\((aq|s|l|g)\)$", re.IGNORECASE)
CHARGE_PATTERN = re.compile(r"\^(?:(\d+))?([+-])$")
FORMULA_TOKEN_PATTERN = re.compile(r"[A-Z][a-z]?|\d+|[()[\]]")
MAX_ATOM_COUNT = 1_000_000
ELEMENTS = frozenset(
    """H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu
    Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La
    Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At
    Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh
    Fl Mc Lv Ts Og""".split()
)


def _package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


class ChemistrySafetyPolicy:
    """Reject hazardous procedural requests without blocking ordinary coursework."""

    procedural = re.compile(
        r"\b(step[- ]by[- ]step|procedure|protocol|synthesi[sz]e|manufacture|prepare|"
        r"exact (?:amounts?|quantities)|scale[- ]?up)\b",
        re.IGNORECASE,
    )
    hazardous = re.compile(
        r"\b(explosive|detonator|poison gas|chemical weapon|nerve agent|ricin|sarin|"
        r"methamphetamine|incendiary|toxic gas)\b",
        re.IGNORECASE,
    )

    def validate(self, text: str) -> None:
        if self.procedural.search(text) and self.hazardous.search(text):
            raise ValidationError(
                "Hazardous chemistry procedures cannot be generated",
                code="unsafe_chemistry_instruction",
            )


class ChemistryTools:
    max_equation_length = 500
    max_species = 20
    max_coefficient = 1_000_000

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        opener: Callable[..., Any] | None = None,
        cache_ttl: timedelta = timedelta(days=7),
    ) -> None:
        self.cache_dir = cache_dir
        self.opener = opener or urllib.request.urlopen
        self.cache_ttl = cache_ttl
        self.safety = ChemistrySafetyPolicy()
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _split_equation(equation: str) -> tuple[str, str, str]:
        matches = [(arrow, equation.count(arrow)) for arrow in ARROWS]
        selected = [(arrow, count) for arrow, count in matches if count]
        if len(selected) != 1 or selected[0][1] != 1:
            raise ValidationError("Equation must contain exactly one supported reaction arrow")
        arrow = selected[0][0]
        left, right = equation.split(arrow)
        if not left.strip() or not right.strip():
            raise ValidationError("Both sides of the reaction are required")
        return left.strip(), right.strip(), arrow

    @staticmethod
    def _split_side(side: str) -> list[str]:
        species = [item.strip() for item in re.split(r"\s+\+\s+", side)]
        if len(species) == 1 and "+" in side:
            species = [item.strip() for item in re.split(r"(?<=[A-Za-z0-9)])\+(?=[A-Z])", side)]
        if not species or any(not item for item in species):
            raise ValidationError("Reaction species must be separated by plus signs")
        return species

    @staticmethod
    def _parse_formula_part(formula: str) -> Counter[str]:
        tokens = FORMULA_TOKEN_PATTERN.findall(formula)
        if not tokens or "".join(tokens) != formula:
            raise ValidationError(f"Unsupported chemical formula: {formula}")
        stack: list[Counter[str]] = [Counter()]
        brackets: list[str] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in "([":
                if len(stack) >= 20:
                    raise ValidationError("Chemical formula grouping exceeds depth 20")
                stack.append(Counter())
                brackets.append(token)
                index += 1
                continue
            if token in ")]":
                expected = "(" if token == ")" else "["
                if len(stack) == 1 or not brackets or brackets.pop() != expected:
                    raise ValidationError(f"Unbalanced grouping in formula: {formula}")
                group = stack.pop()
                index += 1
                has_multiplier = index < len(tokens) and tokens[index].isdigit()
                multiplier = int(tokens[index]) if has_multiplier else 1
                if has_multiplier:
                    index += 1
                if not 1 <= multiplier <= MAX_ATOM_COUNT:
                    raise ValidationError("Formula multipliers must be between 1 and 1000000")
                for element, count in group.items():
                    stack[-1][element] += count * multiplier
                    if stack[-1][element] > MAX_ATOM_COUNT:
                        raise ValidationError("Formula atom counts exceed the configured limit")
                continue
            if token.isdigit():
                raise ValidationError(f"Unexpected coefficient in formula: {formula}")
            if token not in ELEMENTS:
                raise ValidationError(f"Unknown element symbol: {token}")
            index += 1
            has_count = index < len(tokens) and tokens[index].isdigit()
            count = int(tokens[index]) if has_count else 1
            if has_count:
                index += 1
            if count < 1 or count > MAX_ATOM_COUNT:
                raise ValidationError("Formula subscripts must be between 1 and 1000000")
            stack[-1][token] += count
            if stack[-1][token] > MAX_ATOM_COUNT:
                raise ValidationError("Formula atom counts exceed the configured limit")
        if len(stack) != 1:
            raise ValidationError(f"Unbalanced grouping in formula: {formula}")
        return stack[0]

    @classmethod
    def _parse_species(cls, raw: str) -> dict[str, Any]:
        normalized = raw.strip().replace(" ", "")
        coefficient_match = re.match(r"^(\d+)(?=[A-Z([])", normalized)
        source_coefficient = int(coefficient_match.group(1)) if coefficient_match else 1
        if not 1 <= source_coefficient <= cls.max_coefficient:
            raise ValidationError("Source coefficients must be between 1 and 1000000")
        if coefficient_match:
            normalized = normalized[coefficient_match.end() :]
        state_match = STATE_PATTERN.search(normalized)
        state = state_match.group(1).lower() if state_match else None
        if state_match:
            normalized = normalized[: state_match.start()]
        charge_match = CHARGE_PATTERN.search(normalized)
        charge = 0
        if charge_match:
            magnitude = int(charge_match.group(1) or "1")
            if not 1 <= magnitude <= 1_000:
                raise ValidationError("Charge magnitude must be between 1 and 1000")
            charge = magnitude if charge_match.group(2) == "+" else -magnitude
            normalized = normalized[: charge_match.start()]
        if not normalized or len(normalized) > 150:
            raise ValidationError("Chemical formula must contain 1 to 150 characters")
        totals: Counter[str] = Counter()
        for hydrate_part in re.split(r"[·.]", normalized):
            multiplier_match = re.match(r"^(\d+)(?=[A-Z([])", hydrate_part)
            multiplier = int(multiplier_match.group(1)) if multiplier_match else 1
            if not 1 <= multiplier <= MAX_ATOM_COUNT:
                raise ValidationError("Hydrate multipliers must be between 1 and 1000000")
            formula_part = (
                hydrate_part[multiplier_match.end() :] if multiplier_match else hydrate_part
            )
            for element, count in cls._parse_formula_part(formula_part).items():
                totals[element] += count * multiplier
                if totals[element] > MAX_ATOM_COUNT:
                    raise ValidationError("Formula atom counts exceed the configured limit")
        return {
            "source": raw.strip(),
            "formula": normalized,
            "source_coefficient": source_coefficient,
            "state": state,
            "charge": charge,
            "atoms": dict(sorted(totals.items())),
        }

    def balance_equation(self, equation: str) -> dict[str, Any]:
        normalized = equation.strip()
        if (
            not normalized
            or len(normalized) > self.max_equation_length
            or any(ord(character) < 32 for character in normalized)
        ):
            raise ValidationError("Equation must contain 1 to 500 printable characters")
        left_text, right_text, arrow = self._split_equation(normalized)
        left = [self._parse_species(item) for item in self._split_side(left_text)]
        right = [self._parse_species(item) for item in self._split_side(right_text)]
        species = left + right
        if len(species) > self.max_species:
            raise ValidationError("Reaction exceeds the 20 species limit")
        elements = sorted({element for item in species for element in item["atoms"]})
        if not elements:
            raise ValidationError("No chemical elements were recognized")

        def side_totals(items: list[dict[str, Any]], coefficient_key: str) -> Counter[str]:
            totals: Counter[str] = Counter()
            for item in items:
                totals.update(
                    {
                        element: count * item[coefficient_key]
                        for element, count in item["atoms"].items()
                    }
                )
            return totals

        source_left_atoms = side_totals(left, "source_coefficient")
        source_right_atoms = side_totals(right, "source_coefficient")
        source_left_charge = sum(item["charge"] * item["source_coefficient"] for item in left)
        source_right_charge = sum(item["charge"] * item["source_coefficient"] for item in right)
        try:
            import sympy
        except ImportError as exc:
            raise ConfigurationError("Install the 'science' extra to balance equations") from exc
        rows = []
        for element in elements:
            rows.append(
                [item["atoms"].get(element, 0) for item in left]
                + [-item["atoms"].get(element, 0) for item in right]
            )
        if any(item["charge"] for item in species):
            rows.append([item["charge"] for item in left] + [-item["charge"] for item in right])
        basis = sympy.Matrix(rows).nullspace()
        if len(basis) != 1:
            raise ValidationError(
                "Reaction does not have one uniquely determined stoichiometric balance",
                code="unbalanceable_reaction",
            )
        vector = basis[0]
        denominator_lcm = math.lcm(*(int(value.q) for value in vector))
        coefficients = [int(value * denominator_lcm) for value in vector]
        if all(value < 0 for value in coefficients):
            coefficients = [-value for value in coefficients]
        if any(value <= 0 for value in coefficients):
            raise ValidationError(
                "Reaction balance requires a missing or zero species",
                code="unbalanceable_reaction",
            )
        divisor = reduce(math.gcd, coefficients)
        coefficients = [value // divisor for value in coefficients]
        if max(coefficients) > self.max_coefficient:
            raise ValidationError("Balanced coefficients exceed the configured limit")
        for item, coefficient in zip(species, coefficients, strict=True):
            item["verified_coefficient"] = coefficient

        def render(items: list[dict[str, Any]]) -> str:
            values = []
            for item in items:
                coefficient = item["verified_coefficient"]
                suffix = f"({item['state']})" if item["state"] else ""
                charge = ""
                if item["charge"]:
                    magnitude = abs(item["charge"])
                    sign = "+" if item["charge"] > 0 else "-"
                    charge = f"^{magnitude if magnitude != 1 else ''}{sign}"
                prefix = coefficient if coefficient != 1 else ""
                values.append(f"{prefix}{item['formula']}{charge}{suffix}")
            return " + ".join(values)

        left_totals = side_totals(left, "verified_coefficient")
        right_totals = side_totals(right, "verified_coefficient")
        left_charge = sum(item["charge"] * item["verified_coefficient"] for item in left)
        right_charge = sum(item["charge"] * item["verified_coefficient"] for item in right)
        if left_totals != right_totals or left_charge != right_charge:
            raise ConfigurationError(
                "The calculated reaction failed the final conservation check",
                code="chemistry_verification_failed",
            )
        return {
            "tool": "balance_chemical_equation",
            "status": "verified",
            "original_equation": normalized,
            "verified_balanced_equation": f"{render(left)} {arrow} {render(right)}",
            "arrow": arrow,
            "reactants": left,
            "products": right,
            "source_verification": {
                "atoms_balanced": source_left_atoms == source_right_atoms,
                "charge_balanced": source_left_charge == source_right_charge,
                "balanced": (
                    source_left_atoms == source_right_atoms
                    and source_left_charge == source_right_charge
                ),
            },
            "verification": {
                "atoms_balanced": left_totals == right_totals,
                "charge_balanced": left_charge == right_charge,
                "left_atoms": dict(sorted(left_totals.items())),
                "right_atoms": dict(sorted(right_totals.items())),
                "left_charge": left_charge,
                "right_charge": right_charge,
            },
            "conditions_added": False,
            "versions": {"sympy": _package_version("sympy")},
        }

    def analyze_molecule(self, notation: str, notation_format: str = "smiles") -> dict[str, Any]:
        value = notation.strip()
        selected_format = notation_format.strip().casefold()
        if not value or len(value) > 500 or any(ord(character) < 32 for character in value):
            raise ValidationError("Molecule notation must contain 1 to 500 printable characters")
        if selected_format not in {"smiles", "inchi"}:
            raise ValidationError("format must be 'smiles' or 'inchi'")
        try:
            from rdkit import Chem
            from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
        except ImportError as exc:
            raise ConfigurationError(
                "Install the 'chemistry' dependency extra to analyze molecules"
            ) from exc
        molecule = (
            Chem.MolFromSmiles(value) if selected_format == "smiles" else Chem.MolFromInchi(value)
        )
        if molecule is None:
            raise ValidationError("Molecule notation could not be parsed", code="invalid_molecule")
        return {
            "tool": "analyze_molecule",
            "status": "calculated",
            "input": {"notation": value, "format": selected_format},
            "canonical_smiles": Chem.MolToSmiles(molecule, canonical=True),
            "inchi": Chem.MolToInchi(molecule),
            "formula": rdMolDescriptors.CalcMolFormula(molecule),
            "atom_count": molecule.GetNumAtoms(),
            "formal_charge": Chem.GetFormalCharge(molecule),
            "descriptors": {
                "molar_mass_g_mol": Descriptors.MolWt(molecule),
                "exact_mass_da": rdMolDescriptors.CalcExactMolWt(molecule),
                "log_p": Crippen.MolLogP(molecule),
                "hydrogen_bond_donors": Lipinski.NumHDonors(molecule),
                "hydrogen_bond_acceptors": Lipinski.NumHAcceptors(molecule),
            },
            "versions": {"rdkit": _package_version("rdkit")},
        }

    def lookup_chemical_entity(
        self, query: str, *, consent: bool, tenant_id: str
    ) -> dict[str, Any]:
        if not consent:
            raise ValidationError(
                "Explicit consent is required for external chemical lookup",
                code="external_lookup_consent_required",
            )
        normalized = query.strip()
        if (
            not normalized
            or len(normalized) > 200
            or any(ord(character) < 32 for character in normalized)
        ):
            raise ValidationError(
                "Chemical lookup query must contain 1 to 200 printable characters"
            )
        cache_key = hashlib.sha256(f"{tenant_id}\0{normalized.casefold()}".encode()).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.json" if self.cache_dir else None
        if cache_path and cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                retrieved = datetime.fromisoformat(cached["retrieved_at"])
                if datetime.now(UTC) - retrieved <= self.cache_ttl:
                    return {**cached, "cached": True}
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                pass
        properties = "Title,MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,InChI"
        url = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
            f"{quote(normalized, safe='')}/property/{properties}/JSON"
        )
        request = urllib.request.Request(url, headers={"User-Agent": "RankWise/0.1"})
        try:
            with self.opener(request, timeout=5) as response:
                raw = response.read(1_048_577)
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            raise ConfigurationError("PubChem lookup is temporarily unavailable") from exc
        if len(raw) > 1_048_576:
            raise ConfigurationError("PubChem response exceeded the configured size limit")
        try:
            payload = json.loads(raw)
            item = payload["PropertyTable"]["Properties"][0]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ValidationError(
                "PubChem returned no parseable compound", code="chemical_not_found"
            ) from exc
        result = {
            "tool": "lookup_chemical_entity",
            "status": "external_enrichment",
            "external": True,
            "query": normalized,
            "properties": item,
            "source": {"name": "PubChem PUG REST", "url": url},
            "retrieved_at": datetime.now(UTC).isoformat(),
            "cached": False,
        }
        if cache_path:
            temporary = cache_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
            temporary.replace(cache_path)
        return result
