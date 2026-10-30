# aser_column_matcher.py

import pandas as pd
import re


class ASERColumnMatcher:

    def __init__(self, df: pd.DataFrame, dictionary_df: pd.DataFrame):
        self.df = df
        self.dictionary = dictionary_df

    @staticmethod
    def clean(text):
        return re.sub(r"[^a-z0-9]", "", str(text).lower())

    @staticmethod
    def is_binary_series(series):
        """
        Determines whether a column appears to contain
        binary success/failure values.
        """

        values = (
            pd.Series(series)
            .dropna()
            .astype(str)
            .str.strip()
            .str.lower()
            .unique()
        )

        value_set = set(values)

        binary_patterns = [
            {"0", "1"},
            {"0.0", "1.0"},
            {"yes", "no"},
            {"y", "n"},
            {"true", "false"},
            {"pass", "fail"},
            {"correct", "incorrect"}
        ]

        for pattern in binary_patterns:
            if value_set.issubset(pattern):
                return True

        single_value_binary = [
            {"0"},
            {"1"},
            {"0.0"},
            {"1.0"},
            {"yes"},
            {"no"},
            {"true"},
            {"false"}
        ]

        return value_set in single_value_binary

    @staticmethod
    def calculate_confidence(
        match_type,
        binary_flag,
        number_of_matches
    ):
        """
        Simple confidence score (0–1).
        """

        confidence = 0.80 if match_type == "exact" else 0.50

        if binary_flag:
            confidence += 0.20

        if number_of_matches > 1:
            confidence -= 0.10

        return round(min(confidence, 1.00), 2)

    @staticmethod
    def expand_variations(variations, domain):

        expanded = set(variations)

        if domain == "reading":

            prefixes = [
                "reading",
                "literacy"
            ]

        elif domain == "math":

            prefixes = [
                "math",
                "maths",
                "numeracy"
            ]

        else:
            prefixes = []

        for variation in variations:

            expanded.add(variation)

            for prefix in prefixes:

                expanded.add(
                    f"{prefix}{variation}"
                )

                expanded.add(
                    f"{prefix}_{variation}"
                )

        return list(expanded)

    def identify_assessment_columns(self):

        results = {}
        review_required = []
        unmatched = []
        rename_map = {}

        cleaned_columns = {
            self.clean(col): col
            for col in self.df.columns
        }

        for _, row in self.dictionary.iterrows():

            canonical = row["canonical_column"]

            domain = (
                row["domain"]
                if "domain" in self.dictionary.columns
                else None
            )

            variations = [
                self.clean(v.strip())
                for v in str(
                    row["possible_variations"]
                ).split(",")
                if v.strip()
            ]

            variations = self.expand_variations(
                variations,
                domain
            )

            canonical_clean = self.clean(canonical)

            exact_matches = []
            partial_matches = []

            for cleaned_col, original_col in cleaned_columns.items():

                if cleaned_col == canonical_clean:
                    exact_matches.append(original_col)
                    continue

                if cleaned_col in variations:
                    exact_matches.append(original_col)
                    continue

                for variation in variations:

                    if (
                        variation
                        and variation in cleaned_col
                    ):
                        partial_matches.append(original_col)
                        break

            exact_matches = list(dict.fromkeys(exact_matches))
            partial_matches = list(dict.fromkeys(partial_matches))

            if exact_matches:

                binary_flags = {
                    col: self.is_binary_series(
                        self.df[col]
                    )
                    for col in exact_matches
                }

                confidence = self.calculate_confidence(
                    match_type="exact",
                    binary_flag=all(binary_flags.values()),
                    number_of_matches=len(exact_matches)
                )

                status = (
                    "review"
                    if len(exact_matches) > 1
                    else (
                        "matched"
                        if confidence >= 0.90
                        else "review"
                    )
                )

                results[canonical] = {
                    "domain": domain,
                    "columns": exact_matches,
                    "binary_check": binary_flags,
                    "confidence": confidence,
                    "status": status
                }

                if status == "matched":
                    rename_map[
                        exact_matches[0]
                    ] = canonical

                if len(exact_matches) > 1:

                    review_required.append({
                        "canonical_column": canonical,
                        "domain": domain,
                        "reason": "multiple_matches",
                        "columns": exact_matches
                    })

                elif not all(binary_flags.values()):

                    review_required.append({
                        "canonical_column": canonical,
                        "domain": domain,
                        "reason": "non_binary_values",
                        "columns": exact_matches
                    })

            elif partial_matches:

                binary_flags = {
                    col: self.is_binary_series(
                        self.df[col]
                    )
                    for col in partial_matches
                }

                confidence = self.calculate_confidence(
                    match_type="partial",
                    binary_flag=all(binary_flags.values()),
                    number_of_matches=len(partial_matches)
                )

                results[canonical] = {
                    "domain": domain,
                    "columns": partial_matches,
                    "binary_check": binary_flags,
                    "confidence": confidence,
                    "status": "review"
                }

                review_required.append({
                    "canonical_column": canonical,
                    "domain": domain,
                    "reason": "partial_match",
                    "columns": partial_matches
                })

            else:

                unmatched.append({
                    "canonical_column": canonical,
                    "domain": domain
                })

        return {
            "matches": results,
            "rename_map": rename_map,
            "review_required": review_required,
            "unmatched": unmatched
        }