"""Bundle the Python modules and sample data into one self-contained ASERBOT.html."""
import json
from pathlib import Path

src = Path(__file__).resolve().parent
root = src.parent

MODULES = [
    "default_dictionaries.py",
    "dataset_interpreter.py",
    "aser_column_matcher.py",
    "aser_validator.py",
    "aser_scorer.py",
    "aser_analyser_plotly.py",
    "run_app.py",
]


def embed(obj):
    # Stop "</script>" inside embedded text from closing the script tag
    return json.dumps(obj).replace("</", "<\\/")


modules = {name: (src / name).read_text(encoding="utf-8") for name in MODULES}
sample = (root / "Data" / "sample_data.csv").read_text(encoding="utf-8")

html = (
    (src / "app_template.html")
    .read_text(encoding="utf-8")
    .replace("__PY_MODULES__", embed(modules))
    .replace("__SAMPLE_CSV__", embed(sample))
)

out = root / "ASERBOT.html"
out.write_text(html, encoding="utf-8")
print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
