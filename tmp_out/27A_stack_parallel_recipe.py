# Replacement for the 36-input vstack recipe `compute_27A_Enrollment_Stacked`.
# Python recipe: same 36 api-connect inputs + 27A_Enrollment_Muramvya_Back_Up_v2,
# single output 27A_Enrollment_Stacked.
#
# Measured on BURUNDI_27A_ENROLMENT, 2026-08-06:
#   vstack baseline ....... 389 s  (373 s serial reads + ~16 s COPY INTO)
#   this recipe ........... 134 s  (92 s parallel fetch + 42 s write)
#
# The API is the bottleneck, not DSS. Individual fetches slow from ~10 s to ~20-38 s
# under 8-way concurrency, so raising MAX_WORKERS much past 8 buys little.

import dataiku
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor

MAX_WORKERS = 8
ORIGIN_COL = "original_dataset"

INPUTS = [
    "27A_Enrollment_Gishubi", "27A_Enrollment_Bugendana", "27A_Enrollment_Buhinyuza",
    "27A_Enrollment_Bukirasazi", "27A_Enrollment_Butaganzwa", "27A_Enrollment_Bweru",
    "27A_Enrollment_Cankuzo", "27A_Enrollment_Gahombo", "27A_Enrollment_Gasorwe",
    "27A_Enrollment_Gihogazi", "27A_Enrollment_Gisagara", "27A_Enrollment_Gitaramuka",
    "27A_Enrollment_Gitega", "27A_Enrollment_Giteranyi", "27A_Enrollment_Isare",
    "27A_Enrollment_Karusi", "27A_Enrollment_Kiremba", "27A_Enrollment_Kirundo",
    "27A_Enrollment_Makebuko", "27A_Enrollment_Marangara", "27A_Enrollment_Matongo",
    "27A_Enrollment_Mbuye", "27A_Enrollment_Muramvya", "27A_Enrollment_Musongati",
    "27A_Enrollment_Mwumba", "27A_Enrollment_Ngozi", "27A_Enrollment_Nyabihanga",
    "27A_Enrollment_Nyarusange", "27A_Enrollment_Ruyigi", "27A_Enrollment_Tangara",
    "27A_Enrollment_Rutana", "27A_Enrollment_Kabarore", "27A_Enrollment_Muyinga",
    "27A_Enrollment_Kayokwe", "27A_Enrollment_Rango", "27A_Enrollment_Nyabikere",
    "27A_Enrollment_Muramvya_Back_Up_v2",
]

# Mirrors the vstack's "selectedColumns" (UNION mode) so the output schema is unchanged.
SELECTED = [
    "_id", "formhub/uuid", "start", "end", "username", "districtPP", "sitePP",
    "newold_group", "groupPP", "select_farmers", "total_farmers", "selected_count",
    "farmer_repeat_count", "farmer_repeat", "new_client_repeat_old_group",
    "select_existing_gl", "group_leader_signature", "field_officer_signature",
    "__version__", "meta/instanceID", "meta/instanceName", "_xform_id_string",
    "_uuid", "_attachments", "_status", "_geolocation", "_submission_time", "_tags",
    "_notes", "_validation_status", "_submitted_by", "new_group_name",
    "new_group_key_check", "new_client_repeat_new_group",
]


def fetch(name):
    t0 = time.time()
    try:
        df = dataiku.Dataset(name).get_dataframe(infer_with_pandas=False)
        df[ORIGIN_COL] = name
        return name, df, time.time() - t0, None
    except Exception as e:
        return name, None, time.time() - t0, repr(e)[:300]


t_start = time.time()
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    results = list(ex.map(fetch, INPUTS))

frames, errors = [], []
for name, df, dt, err in results:
    print("%-42s %6.1fs  rows=%s" % (name, dt, 0 if df is None else len(df)))
    (errors if err else frames).append((name, err) if err else df)

# Fail loudly rather than silently writing a short table: a district that 500s
# would otherwise just vanish from the stack.
if errors:
    raise Exception("Failed to fetch %d/%d districts: %s" % (
        len(errors), len(INPUTS), [e[0] for e in errors]))

out = pd.concat(frames, ignore_index=True, sort=False)
keep = [c for c in SELECTED if c in out.columns] + [ORIGIN_COL]
out = out[keep].astype(str)

print("stacked rows: %d  cols: %d  fetch+concat: %.1fs" % (
    len(out), len(out.columns), time.time() - t_start))

dataiku.Dataset("27A_Enrollment_Stacked").write_with_schema(out)
print("TOTAL: %.1fs" % (time.time() - t_start))
