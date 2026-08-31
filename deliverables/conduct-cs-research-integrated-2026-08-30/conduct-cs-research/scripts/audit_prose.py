#!/usr/bin/env python3
"""Compare original and revised scientific prose for protected-content drift."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from _common import ValidationError, has_placeholder, read_text

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
SEMANTIC_EVENTS = {
    **SEMANTIC_CATEGORIES,
    "negation": NEGATION_RE,
    "uncertainty": UNCERTAINTY_RE,
    "strong-causal": STRONG_CAUSAL_RE,
    "certainty": CERTAINTY_RE,
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


def semantic_event_sequence(text: str) -> list[str]:
    events: list[tuple[int, int, str]] = []
    for name, pattern in SEMANTIC_EVENTS.items():
        for match in pattern.finditer(text):
            events.append((match.start(), match.end(), name))
    events.sort()
    return [name for _, _, name in events]


def semantic_paragraph_signatures(text: str) -> list[list[str]]:
    paragraphs = [part for part in re.split(r"\n\s*\n", text) if part.strip()]
    return [semantic_event_sequence(paragraph) for paragraph in paragraphs]


def citation_paragraphs(text: str) -> dict[str, list[int]]:
    mapping: dict[str, list[int]] = defaultdict(list)
    paragraphs = [part for part in re.split(r"\n\s*\n", text) if part.strip()]
    for index, paragraph in enumerate(paragraphs):
        for raw in CITE_KEY_RE.findall(paragraph):
            for key in (item.strip() for item in raw.split(",")):
                if key:
                    mapping[key].append(index)
    return dict(mapping)


def parse_protected_spans(text: str) -> list[str]:
    if has_placeholder(text):
        raise ValidationError("protected-spans record contains a placeholder")
    spans: list[str] = []
    declared_none = False
    for line in text.splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        if value.casefold() == "none":
            declared_none = True
            continue
        spans.append(value)
    if declared_none and spans:
        raise ValidationError("protected-spans record mixes None with literal spans")
    if len(spans) != len(set(spans)):
        raise ValidationError("protected-spans record contains duplicates")
    return spans


def protected_span_errors(original: str, revised: str, spans: list[str]) -> list[str]:
    errors: list[str] = []
    for span in spans:
        original_count = original.count(span)
        revised_count = revised.count(span)
        if original_count == 0:
            errors.append(f"protected span is absent from the original: {span!r}")
        elif revised_count != original_count:
            errors.append(
                f"protected span count changed for {span!r}: {original_count} -> {revised_count}"
            )
    return errors


def _protected_token_checks(original: str, revised: str, errors: list[str]) -> None:
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


def _semantic_checks(
    original: str,
    revised: str,
    strict: bool,
    errors: list[str],
    warnings: list[str],
) -> None:
    original_counts = category_counts(original)
    revised_counts = category_counts(revised)
    changed = {
        name: (original_counts[name], revised_counts[name])
        for name in SEMANTIC_CATEGORIES
        if original_counts[name] != revised_counts[name]
    }
    direction_names = {"upward", "downward", "positive", "negative", "before", "after", "supports", "contradicts", "significant"}
    directional = {name: counts for name, counts in changed.items() if name in direction_names}
    scoped = {name: counts for name, counts in changed.items() if name not in direction_names}
    if directional:
        errors.append(f"directional or evidential language changed: {directional}")
    if scoped:
        (errors if strict else warnings).append(f"conditional or scope markers changed: {scoped}")

    original_events = semantic_event_sequence(original)
    revised_events = semantic_event_sequence(revised)
    if original_events != revised_events:
        message = "ordered semantic-event sequence changed; inspect which claim owns each direction, hedge, negation, or causal term"
        (errors if strict else warnings).append(message)
    elif semantic_paragraph_signatures(original) != semantic_paragraph_signatures(revised):
        message = "semantic markers moved between paragraphs; inspect local claim ownership"
        (errors if strict else warnings).append(message)

    checks = (
        ("negation", NEGATION_RE, "count changed; inspect polarity manually"),
        ("uncertainty", UNCERTAINTY_RE, "markers decreased",),
        ("strong causal or proof", STRONG_CAUSAL_RE, "verbs increased"),
        ("certainty", CERTAINTY_RE, "markers increased"),
    )
    for label, pattern, suffix in checks:
        before = len(pattern.findall(original))
        after = len(pattern.findall(revised))
        concerning = before != after if label == "negation" else after > before if label in {"strong causal or proof", "certainty"} else after < before
        if concerning:
            (errors if strict else warnings).append(f"{label} {suffix}: {before} -> {after}")


def audit_text(
    original: str,
    revised: str,
    *,
    strict: bool = False,
    protected_spans: list[str] | None = None,
) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    _protected_token_checks(original, revised, errors)
    errors.extend(protected_span_errors(original, revised, protected_spans or []))
    _semantic_checks(original, revised, strict, errors, warnings)

    if citation_paragraphs(original) != citation_paragraphs(revised):
        (errors if strict else warnings).append(
            "citation paragraph placement changed; inspect citation scope manually"
        )
    if items(TEX_MACRO_RE, original) != items(TEX_MACRO_RE, revised):
        (errors if strict else warnings).append(
            "LaTeX macro inventory changed outside explicitly protected citation/reference commands"
        )

    metrics = {
        "original_characters": len(original),
        "revised_characters": len(revised),
        "original_words": len(re.findall(r"\b\w+\b", original)),
        "revised_words": len(re.findall(r"\b\w+\b", revised)),
        "strict_semantics": strict,
        "protected_spans": len(protected_spans or []),
        "manual_review_required": bool(warnings),
    }
    return {"passed": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}


def audit(
    original_path: Path,
    revised_path: Path,
    *,
    strict: bool = False,
    protected_spans_path: Path | None = None,
) -> dict[str, object]:
    try:
        original = read_text(original_path)
        revised = read_text(revised_path)
        spans = parse_protected_spans(read_text(protected_spans_path)) if protected_spans_path else []
    except ValidationError as exc:
        return {"passed": False, "errors": [str(exc)], "warnings": [], "metrics": {}}
    return audit_text(original, revised, strict=strict, protected_spans=spans)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("revised", type=Path)
    parser.add_argument("--protected-spans", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = audit(
        args.original.expanduser(),
        args.revised.expanduser(),
        strict=args.strict,
        protected_spans_path=args.protected_spans.expanduser() if args.protected_spans else None,
    )
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
