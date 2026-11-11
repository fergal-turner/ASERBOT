# aser_scorer.py

import pandas as pd


class ASERScorer:
    """
    Assumes:

    1. Columns have already been renamed to canonical names.
    2. Validation has already been completed.
    3. Assessment variables are binary success/failure fields.

    Outputs:
        - scored dataframe
        - literacy scale metadata
        - numeracy scale metadata
    """

    LITERACY_SEQUENCE = [
        ("reading_letter", "Letter"),
        ("reading_word", "Word"),
        ("reading_sentence", "Sentence"),
        ("reading_story", "Story"),
        ("reading_comprehension", "Comprehension")
    ]

    def __init__(self,  df: pd.DataFrame, metadata_columns: list, analysis_type: str):
        self.df = df.copy()
        self.metadata_columns = metadata_columns
        self.analysis_type = analysis_type

    # =====================================================
    # HELPERS
    # =====================================================

    @staticmethod
    def to_binary(series):
        """
        Standardises common binary formats to 0/1.
        """

        mapping = {
            "yes": 1,
            "no": 0,
            "y": 1,
            "n": 0,
            "true": 1,
            "false": 0,
            "pass": 1,
            "fail": 0,
            "correct": 1,
            "incorrect": 0,
            "1": 1,
            "0": 0,
            "1.0": 1,
            "0.0": 0
        }

        return (
            series
            .astype(str)
            .str.strip()
            .str.lower()
            .map(mapping)
            .fillna(0)
            .astype(int)
        )

    # =====================================================
    # SCALE BUILDERS
    # =====================================================

    def get_literacy_sequence(self):
        """
        Returns only literacy stages present in the dataset.
        """

        sequence = []

        for col, label in self.LITERACY_SEQUENCE:

            if col in self.df.columns:
                sequence.append((col, label))

        return sequence

    def get_numeracy_sequence(self):
        """
        Builds a dynamic numeracy hierarchy.

        If both number recognition stages exist:

            1. Number Recognition 1-10
            2. Number Recognition 1-99
            3. Addition
            4. Subtraction
            5. Multiplication
            6. Division

        If only one number recognition stage exists:

            1. Number Recognition
            2. Addition
            3. Subtraction
            4. Multiplication
            5. Division
        """

        sequence = []

        has_1_10 = (
            "number_recognition_1_10"
            in self.df.columns
        )

        has_1_99 = (
            "number_recognition_1_99"
            in self.df.columns
        )

        if has_1_10 and has_1_99:

            sequence.extend([
                (
                    "number_recognition_1_10",
                    "Number Recognition 1-10"
                ),
                (
                    "number_recognition_1_99",
                    "Number Recognition 1-99"
                ),
            ])

        elif "number_recognition" in self.df.columns:

            sequence.append(
                (
                    "number_recognition",
                    "Number Recognition"
                )
            )

        for col, label in [
            ("addition", "Addition"),
            ("subtraction", "Subtraction"),
            ("multiplication", "Multiplication"),
            ("division", "Division")
        ]:

            if col in self.df.columns:
                sequence.append((col, label))

        return sequence

    # =====================================================
    # STANDARDISATION
    # =====================================================

    def standardise_columns(self):

        assessment_columns = [
            col
            for col, _ in (
                self.get_literacy_sequence()
                + self.get_numeracy_sequence()
            )
        ]

        for col in assessment_columns:

            self.df[col] = self.to_binary(
                self.df[col]
            )

    # =====================================================
    # SCORING
    # =====================================================

    def calculate_literacy_levels(self):

        sequence = self.get_literacy_sequence()

        self.df["literacy_level"] = 0
        self.df["literacy_label"] = "None"

        for level, (col, label) in enumerate(
            sequence,
            start=1
        ):

            self.df.loc[
                self.df[col] == 1,
                "literacy_level"
            ] = level

            self.df.loc[
                self.df[col] == 1,
                "literacy_label"
            ] = label

        scale = {0: "None"}

        for level, (_, label) in enumerate(
            sequence,
            start=1
        ):
            scale[level] = label

        return scale

    def calculate_numeracy_levels(self):

        sequence = self.get_numeracy_sequence()

        self.df["numeracy_level"] = 0
        self.df["numeracy_label"] = "None"

        for level, (col, label) in enumerate(
            sequence,
            start=1
        ):

            self.df.loc[
                self.df[col] == 1,
                "numeracy_level"
            ] = level

            self.df.loc[
                self.df[col] == 1,
                "numeracy_label"
            ] = label

        scale = {0: "None"}

        for level, (_, label) in enumerate(
            sequence,
            start=1
        ):
            scale[level] = label

        return scale
    
    @staticmethod
    def calculate_change_series(
        df,
        id_col,
        round_col,
        outcome_col,
        baseline_value="baseline",
        endline_value="endline"
    ):
        """
        Returns a Series that can be assigned directly:

        df["literacy_change"] = calculate_change_series(...)

        Change = endline - baseline
        """

        pivot = (
            df[[id_col, round_col, outcome_col]]
            .pivot(
                index=id_col,
                columns=round_col,
                values=outcome_col
            )
        )

        change_lookup = (
            pivot[endline_value]
            - pivot[baseline_value]
        )

        return df[id_col].map(change_lookup)
    
    @staticmethod
    def change_binary_series(
            change_series,
            threshold=1
        ):
            """
            Returns binary Series.

            1 = improved by threshold or more
            0 = otherwise
            """
            return (change_series >= threshold).astype(float).where(
                change_series.notna()
            )
    
    # =====================================================
    # OUTPUT
    # =====================================================

    def keep_canonical_columns(self):

        assessment_columns = [
            col
            for col, _ in (
                self.get_literacy_sequence()
                + self.get_numeracy_sequence()
            )
        ]

        keep_columns = []

        for col in self.metadata_columns:

            if col in self.df.columns:
                keep_columns.append(col)

        for col in assessment_columns:

            if col in self.df.columns:
                keep_columns.append(col)

        keep_columns.extend([
            "literacy_level",
            "literacy_label",
            "numeracy_level",
            "numeracy_label"
        ])

        self.df = self.df[keep_columns].copy()

    # =====================================================
    # MAIN
    # =====================================================

    def run(self):

        self.standardise_columns()

        literacy_scale = (
            self.calculate_literacy_levels()
        )

        numeracy_scale = (
            self.calculate_numeracy_levels()
        )

        self.keep_canonical_columns()

        if max(literacy_scale) > 0:
            self.df["foundational_literacy"] = (
                self.df["literacy_level"] == max(literacy_scale)
            ).astype(int)
        if max(numeracy_scale) > 0:
            self.df["foundational_numeracy"] = (
                self.df["numeracy_level"] == max(numeracy_scale)
            ).astype(int)

        if self.analysis_type == "repeat_measures":

            self.df["literacy_change"] = self.calculate_change_series(
                self.df,
                id_col="uid",
                round_col="round",
                outcome_col="literacy_level"
            )

            self.df["literacy_change_binary"] = self.change_binary_series(
                self.df["literacy_change"]
            )

            self.df["numeracy_change"] = self.calculate_change_series(
                self.df,
                id_col="uid",
                round_col="round",
                outcome_col="numeracy_level"
            )

            self.df["numeracy_change_binary"] = self.change_binary_series(
                self.df["numeracy_change"]
            )

        return {
            "scored_df": self.df,
            "literacy_scale": literacy_scale,
            "numeracy_scale": numeracy_scale,
            "max_literacy_level": max(
                literacy_scale.keys()
            ),
            "max_numeracy_level": max(
                numeracy_scale.keys()
            )
        }