#!/usr/bin/env python3
"""Rank documented journal fit and validate local Q1 evidence records."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from _common import ValidationError, parse_timestamp, read_csv, verify_path_hash

FIT_FIELDS = ["scope_fit", "methods_fit", "audience_fit", "article_fit", "open_science_fit"]
WEIGHTS = {"scope_fit": 0.30, "methods_fit": 0.25, "audience_fit": 0.20, "article_fit": 0.15, "open_science_fit": 0.10}
PROVIDER_ALIASES = {
    "JCR": "JCR",
    "JOURNALCITATIONREPORTS": "JCR",
    "CITESCORE": "CITESCORE",
    "SCOPUSCITESCORE": "CITESCORE",
    "SJR": "SJR",
    "SCIMAGOSJR": "SJR",
}
PROVIDER_DOMAINS = {"JCR": {"jcr.clarivate.com"}, "CITESCORE": {"scopus.com"}, "SJR": {"scimagojr.com"}}
ISSN_RE = re.compile(r"^\d{4}-\d{3}[\dX]$")


def parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def normalize_provider(value: str) -> str | None:
    compact = "".join(character for character in value.upper() if character.isalnum())
    return PROVIDER_ALIASES.get(compact)


def normalize_issn(value: str) -> str:
    return value.strip().upper()


def valid_issn(value: str) -> bool:
    normalized = normalize_issn(value)
    if not ISSN_RE.fullmatch(normalized):
        return False
    digits = normalized.replace("-", "")
    total = sum(int(digit) * weight for digit, weight in zip(digits[:7], range(8, 1, -1)))
    expected = (11 - total % 11) % 11
    check = 10 if digits[-1] == "X" else int(digits[-1])
    return expected == check


def trusted_url(value: str, domains: set[str]) -> bool:
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or port:
        return False
    host = parsed.hostname.lower().rstrip(".")
    if not any(host == domain or host.endswith("." + domain) for domain in domains):
        return False
    return parsed.path not in {"", "/"} or bool(parsed.query)


def journal_identity(row: dict[str, str]) -> tuple[str, str]:
    return (re.sub(r"\s+", " ", row.get("journal", "").strip()).casefold(), normalize_issn(row.get("issn", "")))


def observation_identity(row: dict[str, str], provider: str | None) -> tuple[str, str, str, str, str, str]:
    journal, issn = journal_identity(row)
    return (
        journal,
        issn,
        provider or row.get("provider", "").strip().casefold(),
        row.get("metric_year", "").strip(),
        re.sub(r"\s+", " ", row.get("category", "").strip()).casefold(),
        row.get("evidence_sha256", "").strip().lower(),
    )


def _fit_values(row: dict[str, str], index: int, errors: list[str]) -> dict[str, float] | None:
    values: dict[str, float] = {}
    for field in FIT_FIELDS:
        try:
            value = float(row.get(field, ""))
        except ValueError:
            errors.append(f"row {index}: {field} must be numeric")
            return None
        if not 0 <= value <= 5:
            errors.append(f"row {index}: {field} must be between 0 and 5")
            return None
        values[field] = value
    return values


def _rank_reasons(row: dict[str, str]) -> list[str]:
    rank = row.get("rank", "").strip()
    denominator = row.get("denominator", "").strip()
    if bool(rank) != bool(denominator):
        return ["rank and denominator must be supplied together"]
    if not rank:
        return []
    try:
        rank_value, denominator_value = int(rank), int(denominator)
    except ValueError:
        return ["rank and denominator must be integers"]
    if rank_value < 1 or denominator_value < 1 or rank_value > denominator_value:
        return ["rank and denominator are inconsistent"]
    return []


def _date_reasons(row: dict[str, str], today: date, max_age: int, max_lag: int) -> list[str]:
    reasons: list[str] = []
    try:
        metric_year = int(row.get("metric_year", ""))
    except ValueError:
        reasons.append("metric year is invalid")
    else:
        if metric_year > today.year:
            reasons.append("metric year is in the future")
        elif metric_year < today.year - max_lag:
            reasons.append(f"metric year is older than the allowed {max_lag}-year lag")
    verified = parse_date(row.get("verified_date", ""))
    if verified is None:
        reasons.append("verification date is invalid")
    else:
        age = (today - verified).days
        if age < 0:
            reasons.append("verification date is in the future")
        elif age > max_age:
            reasons.append(f"verification is older than {max_age} days")
    return reasons


def _human_reasons(row: dict[str, str], index: int, today: date) -> list[str]:
    reasons: list[str] = []
    if not row.get("human_verified_by", "").strip():
        reasons.append("human verifier is missing")
    try:
        checked = parse_timestamp(row.get("human_verified_at", ""), field=f"row {index} human_verified_at")
    except ValidationError as exc:
        reasons.append(str(exc))
    else:
        if checked.date() > today:
            reasons.append("human verification time is in the future")
    return reasons


def _q1_reasons(
    root: Path,
    row: dict[str, str],
    index: int,
    provider: str | None,
    today: date,
    max_age: int,
    max_lag: int,
) -> list[str]:
    reasons: list[str] = []
    issn = normalize_issn(row.get("issn", ""))
    if not issn:
        reasons.append("ISSN is missing")
    elif not valid_issn(issn):
        reasons.append("ISSN is malformed or has an invalid checksum")
    if provider is None:
        reasons.append("unrecognized metric provider")
    if row.get("quartile", "").upper() != "Q1":
        reasons.append("quartile is not Q1")
    if not row.get("metric_name", "").strip():
        reasons.append("metric name is missing")
    if not row.get("category", "").strip():
        reasons.append("exact subject category is missing")
    reasons.extend(_rank_reasons(row))
    reasons.extend(_date_reasons(row, today, max_age, max_lag))
    if provider is None or not trusted_url(row.get("verification_url", ""), PROVIDER_DOMAINS.get(provider, set())):
        reasons.append("verification URL is not a specific authoritative provider record")
    try:
        verify_path_hash(root, row.get("evidence_path", "").strip(), row.get("evidence_sha256", "").strip().lower(), label=f"row {index} evidence capture")
    except ValidationError as exc:
        reasons.append(str(exc))
    reasons.extend(_human_reasons(row, index, today))
    return reasons


def _record(row: dict[str, str], values: dict[str, float], provider: str | None, reasons: list[str]) -> dict[str, object]:
    return {
        "journal": row.get("journal", "").strip(),
        "issn": normalize_issn(row.get("issn", "")),
        "fit_score": round(sum(values[field] * WEIGHTS[field] for field in FIT_FIELDS), 3),
        "fit_components": values,
        "q1_verified": not reasons,
        "q1_reasons": reasons,
        "provider": provider or row.get("provider", ""),
        "metric_name": row.get("metric_name", ""),
        "metric_year": row.get("metric_year", ""),
        "category": row.get("category", ""),
        "quartile": row.get("quartile", ""),
        "verified_date": row.get("verified_date", ""),
        "verification_url": row.get("verification_url", ""),
        "evidence_path": row.get("evidence_path", "").strip(),
        "evidence_sha256": row.get("evidence_sha256", "").strip().lower(),
        "human_verified_by": row.get("human_verified_by", "").strip(),
        "human_verified_at": row.get("human_verified_at", "").strip(),
        "notes": row.get("notes", ""),
        "verification_scope": "hash-bound local evidence; remote origin and verifier identity are not authenticated",
    }


def _validate_headers(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    try:
        headers, rows = read_csv(path)
    except ValidationError as exc:
        return [], [str(exc)]
    required = {"journal", "issn", *FIT_FIELDS, "provider", "metric_name", "metric_year", "category", "quartile", "rank", "denominator", "verification_url", "evidence_path", "evidence_sha256", "verified_date", "human_verified_by", "human_verified_at"}
    missing = sorted(required - set(headers))
    return rows, [f"missing columns: {', '.join(missing)}"] if missing else []


def score(path: Path, *, max_verification_age: int = 400, max_metric_lag: int = 2, verified_q1_only: bool = False) -> dict[str, object]:
    if max_verification_age < 0:
        return {"passed": False, "errors": ["max_verification_age must be nonnegative"], "warnings": [], "journals": []}
    if not 0 <= max_metric_lag <= 5:
        return {"passed": False, "errors": ["max_metric_lag must be between 0 and 5"], "warnings": [], "journals": []}
    rows, errors = _validate_headers(path)
    if errors:
        return {"passed": False, "errors": errors, "warnings": [], "journals": []}
    warnings: list[str] = []
    output: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    fit_by_journal: dict[tuple[str, str], dict[str, float]] = {}
    today = date.today()
    root = path.resolve().parent
    for index, row in enumerate(rows, start=2):
        journal = row.get("journal", "").strip()
        if not journal:
            errors.append(f"row {index}: journal is empty")
            continue
        values = _fit_values(row, index, errors)
        if values is None:
            continue
        identity = journal_identity(row)
        if identity in fit_by_journal and fit_by_journal[identity] != values:
            errors.append(f"row {index}: fit components disagree across category records for the same journal and ISSN")
            continue
        fit_by_journal[identity] = values
        provider = normalize_provider(row.get("provider", ""))
        observation = observation_identity(row, provider)
        if observation in seen:
            errors.append(f"row {index}: duplicate journal/ISSN/provider/year/category/evidence record")
            continue
        seen.add(observation)
        reasons = _q1_reasons(root, row, index, provider, today, max_verification_age, max_metric_lag)
        record = _record(row, values, provider, reasons)
        if not verified_q1_only or record["q1_verified"]:
            output.append(record)
        if reasons and row.get("quartile", "").upper() == "Q1":
            warnings.append(f"{journal}: Q1 claim is not locally verified ({'; '.join(reasons)})")
    output.sort(key=lambda item: (-float(item["fit_score"]), str(item["journal"]).casefold(), str(item["category"]).casefold()))
    if verified_q1_only and not output:
        warnings.append("no candidate has a complete, current, hash-bound Q1 evidence record")
    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "journals": output,
        "ranking_basis": "scientific fit first; Q1 is an independently documented eligibility field",
        "assurance_boundary": "Local validation does not retrieve the provider page or authenticate the verifier.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--max-verification-age", type=int, default=400)
    parser.add_argument("--max-metric-lag", type=int, default=2)
    parser.add_argument("--verified-q1-only", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = score(args.csv_file.expanduser(), max_verification_age=args.max_verification_age, max_metric_lag=args.max_metric_lag, verified_q1_only=args.verified_q1_only)
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for item in result["journals"]:
            status = "locally verified Q1 record" if item["q1_verified"] else "Q1 not verified"
            print(f"{item['journal']}: fit={item['fit_score']:.3f}; {status}")
        for item in result["errors"]:
            print(f"ERROR: {item}", file=sys.stderr)
        for item in result["warnings"]:
            print(f"WARNING: {item}", file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
