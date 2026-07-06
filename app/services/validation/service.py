"""Validate generated SEO blocks (length, mode-specific structure, compliance)."""

from __future__ import annotations

import re
from typing import List, Tuple

from app.core.config import Settings
from app.schemas.common import GenerationMode
from app.schemas.content_pipeline import (
    ContentPipelineRequest,
    ValidationCheckResult,
    ValidationReport,
)


class ValidationService:
    """Encapsulate rules so new modes can add validators without touching routers."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def word_count(self, text: str) -> int:
        """Count words by whitespace split (good enough for SEO length targets)."""

        cleaned = text.strip()
        if not cleaned:
            return 0
        return len(cleaned.split())

    def validate(self, text: str, *, mode: GenerationMode) -> Tuple[bool, List[str]]:
        """Return (ok, issues) for legacy generation."""

        issues: List[str] = []
        wc = self.word_count(text)
        lo, hi = self._settings.generation_min_words, self._settings.generation_max_words
        if wc < lo:
            issues.append(f"Word count {wc} is below minimum {lo}.")
        if wc > hi:
            issues.append(f"Word count {wc} exceeds maximum {hi}.")

        if mode == "use_cases_block":
            headings = re.findall(r"\*\*[^*]+\*\*", text)
            if len(headings) < 4:
                issues.append(
                    f"Expected at least 4 bold use-case headings; found {len(headings)}.",
                )
        elif mode == "online_vs_desktop":
            stripped = text.lstrip()
            if re.search(r"(?m)^\s*[-*]\s+", stripped):
                issues.append("Comparison mode must not use bullet lists.")

        return (len(issues) == 0), issues

    def validate_pipeline(
        self,
        text: str,
        *,
        mode: GenerationMode,
        req: ContentPipelineRequest,
    ) -> ValidationReport:
        """Full validation for the content pipeline (LSI, bans, competitors, grounding)."""

        checks: List[ValidationCheckResult] = []
        wc = self.word_count(text)
        lo, hi = self._settings.generation_min_words, self._settings.generation_max_words
        wc_ok = lo <= wc <= hi
        wc_detail = f"{wc} words (target {lo}-{hi})"
        checks.append(
            ValidationCheckResult(name="word_count", passed=wc_ok, detail=wc_detail),
        )

        struct_ok, struct_issues = self.validate(text, mode=mode)
        checks.append(
            ValidationCheckResult(
                name="structure",
                passed=struct_ok,
                detail="; ".join(struct_issues) if struct_issues else None,
            ),
        )

        tlow = text.lower()
        missing_lsi: List[str] = []
        for kw in req.lsi_keywords:
            k = (kw or "").strip()
            if not k:
                continue
            if k.lower() not in tlow:
                missing_lsi.append(k)
        lsi_ok = len(missing_lsi) == 0
        checks.append(
            ValidationCheckResult(
                name="lsi_coverage",
                passed=lsi_ok,
                detail=f"matched {len(req.lsi_keywords) - len(missing_lsi)}/{len(req.lsi_keywords)}",
            ),
        )

        banned_found: List[str] = []
        for phrase in self._settings.banned_ai_phrases_list():
            if phrase.lower() in tlow:
                banned_found.append(phrase)
        banned_ok = len(banned_found) == 0
        checks.append(
            ValidationCheckResult(
                name="banned_ai_phrases",
                passed=banned_ok,
                detail=", ".join(banned_found) if banned_found else None,
            ),
        )

        comp_found: List[str] = []
        for brand in req.competitor_brands:
            b = (brand or "").strip()
            if b and b.lower() in tlow:
                comp_found.append(b)
        comp_ok = len(comp_found) == 0
        checks.append(
            ValidationCheckResult(
                name="competitor_brands",
                passed=comp_ok,
                detail=", ".join(comp_found) if comp_found else None,
            ),
        )

        unsupported_notes = self._feature_grounding_issues(text, req)
        ground_ok = len(unsupported_notes) == 0
        checks.append(
            ValidationCheckResult(
                name="product_feature_grounding",
                passed=ground_ok,
                detail="; ".join(unsupported_notes[:3]) if unsupported_notes else None,
            ),
        )

        passed = all(c.passed for c in checks)
        return ValidationReport(
            passed=passed,
            word_count=wc,
            lsi_required=len([k for k in req.lsi_keywords if (k or "").strip()]),
            lsi_matched=len([k for k in req.lsi_keywords if (k or "").strip()]) - len(missing_lsi),
            missing_lsi_keywords=missing_lsi,
            banned_phrases_found=banned_found,
            competitor_mentions_found=comp_found,
            unsupported_feature_notes=unsupported_notes,
            structure_issues=list(struct_issues),
            checks=checks,
        )

    def _feature_grounding_issues(self, text: str, req: ContentPipelineRequest) -> List[str]:
        """Flag sentences with strong capability claims that lack an allowed feature phrase."""

        notes: List[str] = []
        if not req.product_features:
            return notes
        claim_markers = (
            "includes ",
            "include ",
            "supports ",
            "offer ",
            "offers ",
            "comes with ",
            "lets you ",
            "allows you ",
            "enables ",
        )
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for sent in sentences:
            sl = sent.lower()
            if not any(m in sl for m in claim_markers):
                continue
            matched_any = any(
                (pf or "").strip().lower() in sl
                for pf in req.product_features
                if len((pf or "").strip()) > 2
            )
            if not matched_any:
                preview = sent.strip()[:160] + ("…" if len(sent.strip()) > 160 else "")
                notes.append(f"Claim may lack grounding in product_features: {preview}")
        return notes


def flatten_validation_issues(report: ValidationReport) -> List[str]:
    """Turn a report into rewrite-friendly bullet issues."""

    out: List[str] = []
    for c in report.checks:
        if not c.passed:
            out.append(f"{c.name}: {c.detail or 'failed'}")
    for k in report.missing_lsi_keywords:
        out.append(f"Include LSI keyword: {k}")
    for p in report.banned_phrases_found:
        out.append(f"Remove banned phrase: {p}")
    for b in report.competitor_mentions_found:
        out.append(f"Remove competitor mention: {b}")
    out.extend(report.unsupported_feature_notes)
    out.extend(report.structure_issues)
    return out
