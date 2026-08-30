#!/usr/bin/env python3
"""Compare original and revised scientific prose for protected-content drift."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Callable

from _common import ValidationError, read_text

NUMBER_RE = re.compile(
    r"(?<![\w.+\-−])[+\-−]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?:[eE][+\-−]?\d+)?%?(?!\w|\.\d)"
)
UNIT_RE = re.compile(
    r"(?i)(?<!\w)(?:ps|ns|µs|μs|us|ms|s|min|h|Hz|kHz|MHz|GHz|B|KB|MB|GB|TB|KiB|MiB|GiB|TiB|m|cm|mm|µm|μm|km|g|kg|mg|µg|μg|K|°C|°F|%|pp|ppm|dB|W|kW|V|mV|A|mA)(?!\w)"
)
CITE_PREFIX = (
    r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|parencite|textcite|autocite|footcite|smartcite|supercite|nocite)"
    r"[a-zA-Z*]*(?:\s*\[[^\]]*\]){0,2}\s*"
)
CITE_COMMAND_RE = re.compile(CITE_PREFIX + r"\{[^{}]+\}")
CITE_KEY_RE = re.compile(CITE_PREFIX + r"\{([^{}]+)\}")
XREF_RE = re.compile(r"\\(?:ref|eqref|autoref|pageref|cref|Cref|label)\s*\{([^{}]+)\}")
MATH_RE = re.compile(
    r"\$\$.*?\$\$|(?<!\\)\$(?!\$).*?(?<!\\)\$|\\\[.*?\\\]|\\\(.*?\\\)|\\begin\{(?:equation\*?|align\*?|gather\*?)\}.*?\\end\{(?:equation\*?|align\*?|gather\*?)\}",
    re.DOTALL,
)
CODE_RE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
DOI_RE = re.compile(r"(?i)\b10\.\d{4,9}/[-._;()/:A-Z0-9]+")
URL_RE = re.compile(r"https?://[^\s<>{}\[\]]+")
OPERATOR_RE = re.compile(r"(?:<=|>=|!=|==|≤|≥|≠|≈|=|<|>)")
NEGATION_RE = re.compile(r"(?i)\b(?:no|not|never|neither|nor|without|cannot|can't|doesn't|didn't|isn't|aren't|wasn't|weren't)\b")
UNCERTAINTY_RE = re.compile(r"(?i)\b(?:may|might|could|suggests?|appears?|likely|possibly|approximately|uncertain|compatible with)\b")
STRONG_CAUSAL_RE = re.compile(r"(?i)\b(?:causes?|caused|leads? to|results? in|determines?|proves?|demonstrates?|establishes?|ensures?)\b")
CERTAINTY_RE = re.compile(r"(?i)\b(?:clearly|definitively|conclusively|undoubtedly|always|never|guarantees?|certainly)\b")


def _trim_url(value: str) -> str:
    return value.rstrip(".,;:!?")


def _trim_doi(value: str) -> str:
    return value.rstrip(".,;:")


def items(
    pattern: re.Pattern[str],
    text: str,
    *,
    split_commas: bool = False,
    normalize: Callable[[str], str] | None = None,
) -> Counter[str]:
    values: list[str] = []
    for match in pattern.findall(text):
        if isinstance(match, tuple):
            match = "".join(match)
        candidates = [item.strip() for item in match.split(",") if item.strip()] if split_commas else [match.strip()]
        for value in candidates:
            value = re.sub(r"\s+", " ", value)
            if normalize is not None:
                value = normalize(value)
            values.append(value)
    return Counter(values)


def delta(label: str, original: Counter[str], revised: Counter[str], errors: list[str]) -> None:
    removed = list((original - revised).elements())
    added = list((revised - original).elements())
    if removed or added:
        errors.append(f"{label} changed; removed={removed[:12]!r}, added={added[:12]!r}")


def audit(original_path: Path, revised_path: Path, *, strict: bool = False) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        original = read_text(original_path)
        revised = read_text(revised_path)
    except ValidationError as exc:
        return {"passed": False, "errors": [str(exc)], "warnings": [], "metrics": {}}

    delta("numbers", items(NUMBER_RE, original), items(NUMBER_RE, revised), errors)
    delta("units", items(UNIT_RE, original), items(UNIT_RE, revised), errors)
    delta("comparison operators", items(OPERATOR_RE, original), items(OPERATOR_RE, revised), errors)
    delta("citation commands", items(CITE_COMMAND_RE, original), items(CITE_COMMAND_RE, revised), errors)
    delta("citation keys", items(CITE_KEY_RE, original, split_commas=True), items(CITE_KEY_RE, revised, split_commas=True), errors)
    delta("labels and cross-references", items(XREF_RE, original), items(XREF_RE, revised), errors)
    delta("mathematics", items(MATH_RE, original), items(MATH_RE, revised), errors)
    delta("code spans", items(CODE_RE, original), items(CODE_RE, revised), errors)
    delta("DOIs", items(DOI_RE, original, normalize=_trim_doi), items(DOI_RE, revised, normalize=_trim_doi), errors)
    delta("URLs", items(URL_RE, original, normalize=_trim_url), items(URL_RE, revised, normalize=_trim_url), errors)

    original_neg = len(NEGATION_RE.findall(original))
    revised_neg = len(NEGATION_RE.findall(revised))
    if original_neg != revised_neg:
        message = f"negation count changed from {original_neg} to {revised_neg}; inspect polarity manually"
        (errors if strict else warnings).append(message)

    original_uncertainty = len(UNCERTAINTY_RE.findall(original))
    revised_uncertainty = len(UNCERTAINTY_RE.findall(revised))
    if revised_uncertainty < original_uncertainty:
        message = f"uncertainty markers decreased from {original_uncertainty} to {revised_uncertainty}"
        (errors if strict else warnings).append(message)

    original_causal = len(STRONG_CAUSAL_RE.findall(original))
    revised_causal = len(STRONG_CAUSAL_RE.findall(revised))
    if revised_causal > original_causal:
        message = f"strong causal or proof verbs increased from {original_causal} to {revised_causal}"
        (errors if strict else warnings).append(message)

    original_certainty = len(CERTAINTY_RE.findall(original))
    revised_certainty = len(CERTAINTY_RE.findall(revised))
    if revised_certainty > original_certainty:
        message = f"certainty markers increased from {original_certainty} to {revised_certainty}"
        (errors if strict else warnings).append(message)

    metrics = {
        "original_characters": len(original),
        "revised_characters": len(revised),
        "original_words": len(re.findall(r"\b\w+\b", original)),
        "revised_words": len(re.findall(r"\b\w+\b", revised)),
        "strict_semantics": strict,
    }
    return {"passed": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("revised", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = audit(args.original.expanduser(), args.revised.expanduser(), strict=args.strict)
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("PASS" if result["passed"] else "FAIL")
        for item in result["errors"]:
            print(f"ERROR: {item}")
        for item in result["warnings"]:
            print(f"WARNING: {item}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
