#!/usr/bin/env python3
"""Rank documented journal fit while independently validating Q1 records."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from _common import ValidationError, read_csv

FIT_FIELDS = ["scope_fit", "methods_fit", "audience_fit", "article_fit", "open_science_fit"]
DEFAULT_WEIGHTS = {
    "scope_fit": 0.30,
    "methods_fit": 0.25,
    "audience_fit": 0.20,
    "article_fit": 0.15,
    "open_science_fit": 0.10,
}
PROVIDERS = {"JCR", "CITESCORE", "SJR"}


def parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def trusted_url(value: str, domains: list[str]) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    if not domains:
        return True
    host = parsed.hostname.lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def score(path: Path, *, max_verification_age: int = 400, trusted_domains: list[str] | None = None) -> dict[str, object]:
    trusted_domains = [item.lower().rstrip(".") for item in (trusted_domains or [])]
    try:
        headers, rows = read_csv(path)
    except ValidationError as exc:
        return {"passed": False, "errors": [str(exc)], "warnings": [], "journals": []}
    required = {"journal", *FIT_FIELDS, "provider", "metric_year", "category", "quartile", "verification_url", "verified_date"}
    missing = sorted(required - set(headers))
    if missing:
        return {"passed": False, "errors": [f"missing columns: {', '.join(missing)}"], "warnings": [], "journals": []}

    errors: list[str] = []
    warnings: list[str] = []
    output: list[dict[str, object]] = []
    today = date.today()
    for index, row in enumerate(rows, start=2):
        journal = row.get("journal", "").strip()
        if not journal:
            errors.append(f"row {index}: journal is empty")
            continue
        values: dict[str, float] = {}
        valid_fit = True
        for field in FIT_FIELDS:
            try:
                value = float(row.get(field, ""))
            except ValueError:
                errors.append(f"row {index}: {field} must be numeric")
                valid_fit = False
                continue
            if not 0 <= value <= 5:
                errors.append(f"row {index}: {field} must be between 0 and 5")
                valid_fit = False
            values[field] = value
        if not valid_fit:
            continue
        fit_score = sum(values[field] * DEFAULT_WEIGHTS[field] for field in FIT_FIELDS)

        q1_reasons: list[str] = []
        provider = row.get("provider", "").upper().replace(" ", "")
        if provider not in PROVIDERS:
            q1_reasons.append("unrecognized metric provider")
        if row.get("quartile", "").upper() != "Q1":
            q1_reasons.append("quartile is not Q1")
        if not row.get("category", "").strip():
            q1_reasons.append("exact subject category is missing")
        try:
            metric_year = int(row.get("metric_year", ""))
        except ValueError:
            metric_year = 0
            q1_reasons.append("metric year is invalid")
        else:
            if metric_year > today.year or metric_year < today.year - 4:
                q1_reasons.append("metric year is implausible or stale")
        verified = parse_date(row.get("verified_date", ""))
        if verified is None:
            q1_reasons.append("verification date is invalid")
        else:
            age = (today - verified).days
            if age < 0:
                q1_reasons.append("verification date is in the future")
            elif age > max_verification_age:
                q1_reasons.append(f"verification is older than {max_verification_age} days")
        if not trusted_url(row.get("verification_url", ""), trusted_domains):
            q1_reasons.append("verification URL is not an allowed HTTPS source")

        record = {
            "journal": journal,
            "fit_score": round(fit_score, 3),
            "fit_components": values,
            "q1_verified": not q1_reasons,
            "q1_reasons": q1_reasons,
            "provider": row.get("provider", ""),
            "metric_year": row.get("metric_year", ""),
            "category": row.get("category", ""),
            "quartile": row.get("quartile", ""),
            "verified_date": row.get("verified_date", ""),
            "verification_url": row.get("verification_url", ""),
            "notes": row.get("notes", ""),
        }
        output.append(record)
        if q1_reasons and row.get("quartile", "").upper() == "Q1":
            warnings.append(f"{journal}: Q1 claim is not verified ({'; '.join(q1_reasons)})")

    output.sort(key=lambda item: (bool(item["q1_verified"]), float(item["fit_score"])), reverse=True)
    return {"passed": not errors, "errors": errors, "warnings": warnings, "journals": output}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--max-verification-age", type=int, default=400)
    parser.add_argument("--trusted-domain", action="append", default=[])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = score(
        args.csv_file.expanduser(),
        max_verification_age=args.max_verification_age,
        trusted_domains=args.trusted_domain,
    )
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for item in result["journals"]:
            status = "verified Q1" if item["q1_verified"] else "Q1 not verified"
            print(f"{item['journal']}: fit={item['fit_score']:.3f}; {status}")
        for item in result["errors"]:
            print(f"ERROR: {item}", file=sys.stderr)
        for item in result["warnings"]:
            print(f"WARNING: {item}", file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
