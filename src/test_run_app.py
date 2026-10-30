import json
from pathlib import Path
from run_app import detect_columns, run_analysis

csv = (Path(__file__).resolve().parent.parent / "Data" / "sample_data.csv").read_text()
d = json.loads(detect_columns(csv))
print(d["ok"], d["rows"])
for f in d["metadata_fields"] + d["aser_fields"]:
    print(f["canonical"], "|", f["status"], "|", f["selected"], "|", f.get("candidates"))

r = json.loads(run_analysis(csv))
print("auto", r["ok"], len(r["figures"]), r["log"]["errors"], r["log"]["warnings"])

m = {f["canonical"]: f["selected"] for f in d["metadata_fields"] + d["aser_fields"] if f["selected"]}
r = json.loads(run_analysis(csv, json.dumps(m)))
print("explicit", r["ok"], len(r["figures"]))

m["region"] = m["sex"]
r = json.loads(run_analysis(csv, json.dumps(m)))
print("duplicate", r["ok"], r["log"]["errors"])
