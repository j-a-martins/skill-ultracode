#!/usr/bin/env python3
"""Compare original and revised scientific prose for protected-content drift."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from _common import ValidationError, read_text

NUMBER_RE = re.compile(
    r"(?<![\w.+\-−–—])(?:[+\-−]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?:[eE][+\-−]?\d+)?(?:\s*%)?)(?!\w|\.\d)"
)
UNIT_RE = re.compile(
    r"(?i)(?<!\w)(?:ps|ns|µs|μs|us|ms|min|sec|seconds?|hours?|Hz|kHz|MHz|GHz|bytes?|KB|MB|GB|TB|KiB|MiB|GiB|TiB|cm|mm|µm|μm|km|kg|mg|µg|μg|°C|°F|ppm|dB|kW|mV|mA)(?!\w)"
)
CITE_PREFIX = (
    r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|citeyearpar|parencite|textcite|autocite|footcite|smartcite|supercite|fullcite|nocite)"
    r"[a-zA-Z*]*(?:\s*\[[^\]]*\]){0,2}\s*"
)
CITE_COMMAND_RE = re.compile(CITE_PREFIX + r"\{[^{}]+\}")
CITE_KEY_RE = re.compile(CITE_PREFIX + r"\{([^{}]+)\}")
XREF_COMMAND_RE = re.compile(r"\\(?:ref|eqref|autoref|pageref|cref|Cref|label)\s*\{[^{}]+\}")
XREF_KEY_RE = re.compile(r"\\(?:ref|eqref|autoref|pageref|cref|Cref|label)\s*\{([^{}]+)\}")
MATH_RE = re.compile(
    r"\$\$.*?\$\$|(?<!\\)\$(?!\$).*?(?<!\\)\$|\\\[.*?\\\]|\\\(.*?\\\)|\\begin\{(?:equation\*?|align\*?|alignat\*?|gather\*?|multline\*?)\}.*?\\end\{(?:equation\*?|align\*?|alignat\*?|gather\*?|multline\*?)\}",
    re.DOTALL,
)
CODE_RE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
DOI_RE = re.compile(r"(?i)\b10\.\d{4,9}/[-._;()/:A-Z0-9]+")
URL_RE = re.compile(r"https?://[^\s<>{}\[\]]+")
OPERATOR_RE = re.compile(r"(?:<=|>=|!=|==|≤|≥|≠|≈|≲|≳|±|=|<|>)")
TEX_MACRO_RE = re.compile(r"\\[A-Za-z@]+\*?")
NEGATION_RE = re.compile(r"(?i)\b(?:no|not|never|neither|nor|without|cannot|can't|doesn't|didn't|isn't|aren't|wasn't|weren't|non[- ]?significant)\b")
UNCERTAINTY_RE = re.compile(r"(?i)\b(?:may|might|could|suggests?|appears?|likely|possibly|approximately|uncertain|compatible with|cannot exclude|tentative(?:ly)?)\b")
STRONG_CAUSAL_RE = re.compile(r"(?i)\b(?:causes?|caused|leads? to|results? in|determines?|proves?|demonstrates?|establishes?|ensures?)\b")
CERTAINTY_RE = re.compile(r"(?i)\b(?:clearly|definitively|conclusively|undoubtedly|guarantees?|certainly|universally)\b")

SEMANTIC_CATEGORIES: dict[str, re.Pattern[str]] = {
    "upward": re.compile(r"(?i)\b(?:increase[ds]?|increasing|rise[sn]?|rose|gain(?:ed|s)?|improv(?:e|ed|es|ing)|higher|greater|larger|more|above|exceed(?:ed|s|ing)?)\b"),
    "downward": re.compile(r"(?i)\b(?:decrease[ds]?|decreasing|fell|fall(?:en|ing|s)?|drop(?:ped|s|ping)?|reduc(?:e|ed|es|ing)|lower|smaller|less|below|wors(?:e|ened|ens|ening)|deteriorat(?:e|ed|es|ing))\b"),
    "positive": re.compile(r"(?i)\b(?:positive|beneficial|favorable|advantageous)\b"),
    "negative": re.compile(r"(?i)\b(?:negative|harmful|adverse|unfavorable|detrimental)\b"),
    "before": re.compile(r"(?i)\b(?:before|earlier|preced(?:e|ed|es|ing)|prior to)\b"),
    "after": re.compile(r"(?i)\b(?:after|later|follow(?:ed|s|ing)|subsequent(?:ly)?|post[- ]?)\b"),
    "supports": re.compile(r"(?i)\b(?:support(?:s|ed|ing)?|confirm(?:s|ed|ing)?|consistent with|corroborat(?:e|ed|es|ing))\b"),
    "contradicts": re.compile(r"(?i)\b(?:contradict(?:s|ed|ing)?|refut(?:e|ed|es|ing)|inconsistent with|conflict(?:s|ed|ing)? with)\b"),
    "significant": re.compile(r"(?i)\b(?:statistically significant|significant(?:ly)?)\b"),
    "conditional": re.compile(r"(?i)\b(?:if|unless|provided that|conditional(?:ly)?|only if|only when|except when|subject to)\b"),
    "universal": re.compile(r"(?i)\b(?:all|every|everyone|always|none|never|universally)\b"),
    "restrictive": re.compile(r"(?i)\b(?:only|solely|exclusively|limited to|restricted to)\b"),
}


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


def category_counts(text: str) -> Counter[str]:
    return Counter({name: len(pattern.findall(text)) for name, pattern in SEMANTIC_CATEGORIES.items()})


def citation_paragraphs(text: str) -> dict[str, list[int]]:
    mapping: dict[str, list[int]] = defaultdict(list)
    paragraphs = [part for part in re.split(r"\n\s*\n", text) if part.strip()]
    for index, paragraph in enumerate(paragraphs):
        for raw in CITE_KEY_RE.findall(paragraph):
            for key in (item.strip() for item in raw.split(",")):
                if key:
                    mapping[key].append(index)
    return dict(mapping)


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
    delta("LaTeX reference commands", items(XREF_COMMAND_RE, original), items(XREF_COMMAND_RE, revised), errors)
    delta("LaTeX reference keys", items(XREF_KEY_RE, original), items(XREF_KEY_RE, revised), errors)
    delta("mathematics", items(MATH_RE, original), items(MATH_RE, revised), errors)
    delta("code spans", items(CODE_RE, original), items(CODE_RE, revised), errors)
    delta("DOIs", items(DOI_RE, original, normalize=_trim_doi), items(DOI_RE, revised, normalize=_trim_doi), errors)
    delta("URLs", items(URL_RE, original, normalize=_trim_url), items(URL_RE, revised, normalize=_trim_url), errors)

    semantic_original = category_counts(original)
    semantic_revised = category_counts(revised)
    changed_categories = {
        name: (semantic_original[name], semantic_revised[name])
        for name in SEMANTIC_CATEGORIES
        if semantic_original[name] != semantic_revised[name]
    }
    direction_names = {"upward", "downward", "positive", "negative", "before", "after", "supports", "contradicts", "significant"}
    directional = {name: counts for name, counts in changed_categories.items() if name in direction_names}
    scoped = {name: counts for name, counts in changed_categories.items() if name not in direction_names}
    if directional:
        errors.append(f"directional or evidential language changed: {directional}")
    if scoped:
        message = f"conditional or scope markers changed: {scoped}"
        (errors if strict else warnings).append(message)

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

    citation_locations_before = citation_paragraphs(original)
    citation_locations_after = citation_paragraphs(revised)
    if citation_locations_before != citation_locations_after:
        message = "citation paragraph placement changed; inspect citation scope manually"
        (errors if strict else warnings).append(message)

    macro_before = items(TEX_MACRO_RE, original)
    macro_after = items(TEX_MACRO_RE, revised)
    if macro_before != macro_after:
        message = "LaTeX macro inventory changed outside explicitly protected citation/reference commands"
        (errors if strict else warnings).append(message)

    metrics = {
        "original_characters": len(original),
        "revised_characters": len(revised),
        "original_words": len(re.findall(r"\b\w+\b", original)),
        "revised_words": len(re.findall(r"\b\w+\b", revised)),
        "strict_semantics": strict,
        "manual_review_required": bool(warnings),
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
