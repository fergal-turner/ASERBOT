# aser_validator.py

import pandas as pd


class ASERValidator:

    READING_COLUMNS = [
        "reading_letter",
        "reading_word",
        "reading_sentence",
        "reading_story",
        "reading_comprehension"
    ]

    MATH_COLUMNS = [
        "number_recognition",
        "number_recognition_1_10",
        "number_recognition_1_99",
        "addition",
        "subtraction",
        "multiplication",
        "division"
    ]

    def __init__(
        self,
        df: pd.DataFrame,
        metadata: dict = None
    ):

        self.df = df
        self.metadata = metadata or {}

        self.errors = []
        self.warnings = []
        self.info = {}

    # =====================================================
    # HELPERS
    # =====================================================

    @staticmethod
    def is_binary(series):

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


    # =====================================================
    # DATASET CHECKS
    # =====================================================

    def validate_dataset_structure(self):

        rows = len(self.df)
        cols = len(self.df.columns)

        self.info["rows"] = rows
        self.info["columns"] = cols

        if rows == 0:
            self.errors.append(
                "Dataset contains no rows."
            )

        if cols == 0:
            self.errors.append(
                "Dataset contains no columns."
            )

    def validate_duplicate_rows(self):

        duplicates = self.df.duplicated().sum()

        self.info["duplicate_rows"] = int(
            duplicates
        )

        if duplicates > 0:

            self.warnings.append(
                f"{duplicates:,} duplicate rows detected."
            )

    def validate_empty_columns(self):

        empty_columns = []

        for col in self.df.columns:

            if self.df[col].isna().all():
                empty_columns.append(col)

        self.info["empty_columns"] = (
            empty_columns
        )

        if empty_columns:

            self.warnings.append(
                f"{len(empty_columns)} completely empty columns found."
            )

    # =====================================================
    # METADATA CHECKS
    # =====================================================

    def validate_metadata_columns(self):

        expected = [
            "school",
            "uid",
            "grade",
            "sex"
        ]

        found = {}

        for item in expected:

            found[item] = (
                item in self.df.columns
            )

        self.info["metadata_found"] = found

        if not found["school"]:

            self.errors.append(
                "No school column found."
            )

        if not found["grade"]:

            self.warnings.append(
                "No grade column found."
            )

        if not found["sex"]:

            self.warnings.append(
                "No sex column found."
            )

        if not found["uid"]:

            self.warnings.append(
                "No uid column found."
            )

    # =====================================================
    # CHILD ID CHECKS
    # =====================================================

    def validate_child_ids(self):

        if "uid" not in self.df.columns:
            return

        duplicates = (
            self.df["uid"]
            .duplicated()
            .sum()
        )

        self.info[
            "duplicate_uids"
        ] = int(duplicates)

        if duplicates > 0:

            self.warnings.append(
                f"{duplicates:,} duplicate UIDs detected."
            )

    # =====================================================
    # ASSESSMENT CHECKS
    # =====================================================

    def validate_assessment_columns(self):

        assessment_summary = {}

        assessment_columns = (
            self.READING_COLUMNS
            + self.MATH_COLUMNS
        )

        for col in assessment_columns:

            if col not in self.df.columns:
                continue

            missing_pct = round(
                self.df[col]
                .isna()
                .mean()
                * 100,
                2
            )

            binary_flag = self.is_binary(
                self.df[col]
            )

            assessment_summary[col] = {
                "missing_pct": missing_pct,
                "binary": binary_flag
            }

            if not binary_flag:

                self.warnings.append(
                    f"{col} does not appear binary."
                )

            if missing_pct > 20:

                self.warnings.append(
                    f"{col} has "
                    f"{missing_pct}% missing values."
                )

        self.info[
            "assessment_summary"
        ] = assessment_summary

    # =====================================================
    # DOMAIN COVERAGE
    # =====================================================

    def validate_domain_coverage(self):

        reading_found = sum(
            col in self.df.columns
            for col in self.READING_COLUMNS
        )

        math_found = sum(
            col in self.df.columns
            for col in self.MATH_COLUMNS
        )

        self.info["reading_coverage"] = round(
            reading_found
            / len(self.READING_COLUMNS),
            2
        )

        self.info["math_coverage"] = round(
            math_found
            / len(self.MATH_COLUMNS),
            2
        )

        if reading_found == 0:

            self.warnings.append(
                "No reading variables found."
            )

        if math_found == 0:

            self.warnings.append(
                "No mathematics variables found."
            )

    # =====================================================
    # READING PROGRESSION
    # =====================================================

    def validate_reading_progression(self):

        if (
            "reading_letter"
            not in self.df.columns
        ):
            return

        if (
            "reading_story"
            not in self.df.columns
        ):
            return

        impossible = (
            (self.df["reading_letter"] == 0)
            &
            (self.df["reading_story"] == 1)
        ).sum()

        self.info[
            "story_without_letter"
        ] = int(impossible)

        if impossible > 0:

            self.warnings.append(
                f"{impossible:,} children passed "
                f"reading_story but failed "
                f"reading_letter."
            )

    # =====================================================
    # MAIN VALIDATION
    # =====================================================

    def validate(self):

        self.validate_dataset_structure()

        self.validate_duplicate_rows()

        self.validate_empty_columns()

        self.validate_metadata_columns()

        self.validate_child_ids()

        self.validate_assessment_columns()

        self.validate_domain_coverage()

        self.validate_reading_progression()

        return {
            "dataset_ready":
                len(self.errors) == 0,

            "status":
                "success"
                if len(self.errors) == 0
                else "error",

            "errors":
                self.errors,

            "warnings":
                self.warnings,

            "info":
                self.info
        }