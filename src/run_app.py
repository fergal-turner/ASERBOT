"""Browser-safe entry points: no prompts, returns JSON for the HTML app.

Two stages so the user can review column matches in the UI:
  detect_columns(...)  -> proposed field -> dataset-column mappings
  run_analysis(...)    -> validate, score and plot using confirmed mappings
"""
import io
import json

import pandas as pd

from default_dictionaries import get_default_metadata_df, get_default_aser_df
from dataset_interpreter import DataInterpreter
from aser_column_matcher import ASERColumnMatcher
from aser_validator import ASERValidator
from aser_scorer import ASERScorer
from aser_analyser_plotly import ASER_Analyser_Plotly


def _read_dictionary(csv_text, default_fn):
    if csv_text and csv_text.strip():
        return pd.read_csv(io.StringIO(csv_text))
    return default_fn()


def _detect(df, metadata_df, aser_df):
    """Return (metadata_fields, aser_fields) with proposed dataset columns."""
    interp = DataInterpreter(df, metadata_df).identify_columns()
    matched_meta = interp["metadata"]  # canonical -> original column

    # Same order as the original pipeline: ASER matching sees renamed metadata columns
    renamed = df.rename(columns=interp["rename_map"])
    match = ASERColumnMatcher(renamed, aser_df).identify_assessment_columns()
    back = {canon: orig for orig, canon in interp["rename_map"].items()}

    metadata_fields = []
    for _, row in metadata_df.iterrows():
        canonical = row["canonical_column"]
        metadata_fields.append({
            "canonical": canonical,
            "group": str(row.get("dimension", "")),
            "role": str(row.get("role", "")),
            "selected": matched_meta.get(canonical),
            "status": "matched" if canonical in matched_meta else "unmatched",
        })

    aser_fields = []
    for _, row in aser_df.iterrows():
        canonical = row["canonical_column"]
        found = match["matches"].get(canonical)
        candidates = [back.get(c, c) for c in found["columns"]] if found else []
        status = found["status"] if found else "unmatched"

        # Auto-select clear matches; ambiguous ones are left for the user
        selected = None
        if status == "matched" or len(candidates) == 1:
            selected = candidates[0]

        aser_fields.append({
            "canonical": canonical,
            "group": str(row.get("domain", "")),
            "selected": selected,
            "status": status,
            "candidates": candidates,
            "confidence": found["confidence"] if found else None,
        })

    return metadata_fields, aser_fields


def detect_columns(csv_text, metadata_csv=None, aser_csv=None):
    """Return JSON describing the dataset columns and proposed matches."""
    try:
        df = pd.read_csv(io.StringIO(csv_text))
        metadata_df = _read_dictionary(metadata_csv, get_default_metadata_df)
        aser_df = _read_dictionary(aser_csv, get_default_aser_df)
        metadata_fields, aser_fields = _detect(df, metadata_df, aser_df)

        samples = {
            str(col): [str(v) for v in df[col].dropna().unique()[:3]]
            for col in df.columns
        }

        return json.dumps({
            "ok": True,
            "rows": len(df),
            "columns": [str(c) for c in df.columns],
            "samples": samples,
            "metadata_fields": metadata_fields,
            "aser_fields": aser_fields,
        })
    except Exception as exc:
        return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def run_analysis(csv_text, mappings_json=None, metadata_csv=None, aser_csv=None):
    """Return JSON: {ok, log, figures}.

    mappings_json: JSON object {canonical_field: dataset_column}. If omitted,
    the automatic matches from detect_columns are used.
    """
    log = {
        "rows": 0,
        "analysis_type": None,
        "mappings": {},
        "unmapped": [],
        "errors": [],
        "warnings": [],
    }

    def finish(ok, figures=None):
        return json.dumps({"ok": ok, "log": log, "figures": figures or []})

    try:
        df = pd.read_csv(io.StringIO(csv_text))
        log["rows"] = len(df)

        metadata_df = _read_dictionary(metadata_csv, get_default_metadata_df)
        aser_df = _read_dictionary(aser_csv, get_default_aser_df)

        if mappings_json:
            mappings = json.loads(mappings_json)
        else:
            meta_fields, aser_fields = _detect(df, metadata_df, aser_df)
            mappings = {
                f["canonical"]: f["selected"]
                for f in meta_fields + aser_fields
                if f["selected"]
            }

        mappings = {k: v for k, v in mappings.items() if v}

        used = {}
        for canonical, col in mappings.items():
            if col not in df.columns:
                log["errors"].append(f"Column '{col}' (for {canonical}) is not in the dataset.")
            used.setdefault(col, []).append(canonical)
        for col, fields in used.items():
            if len(fields) > 1:
                log["errors"].append(f"Column '{col}' is mapped to more than one field: {', '.join(fields)}.")
        if log["errors"]:
            return finish(False)

        log["mappings"] = dict(mappings)
        all_fields = list(metadata_df["canonical_column"]) + list(aser_df["canonical_column"])
        log["unmapped"] = [f for f in all_fields if f not in mappings]

        rename_map = {col: canonical for canonical, col in mappings.items()}
        # Unmapped columns that share a name with a target field would create duplicates
        drop = [c for c in df.columns if c not in rename_map and c in mappings]
        df = df.drop(columns=drop).rename(columns=rename_map)

        metadata_columns = [
            c for c in metadata_df["canonical_column"] if c in mappings
        ]

        validation = ASERValidator(
            df=df, metadata={c: c for c in metadata_columns}
        ).validate()
        log["errors"] = list(validation["errors"])
        log["warnings"] = list(validation["warnings"])

        if not validation["dataset_ready"]:
            return finish(False)

        scored = ASERScorer(df=df, metadata_columns=metadata_columns).run()["scored_df"]

        analyser = ASER_Analyser_Plotly(
            scored, metadata_df.set_index("canonical_column").to_dict(orient="index")
        )
        log["analysis_type"] = analyser.detect_analysis_type()

        figures = [
            {"section": r["section"], "title": r["title"], "figure": r["figure"].to_json()}
            for r in analyser.run()
        ]
        return finish(True, figures)

    except Exception as exc:
        log["errors"].append(f"{type(exc).__name__}: {exc}")
        return finish(False)
