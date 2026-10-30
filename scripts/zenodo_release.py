"""Publish a GitHub release of a Tum-Soil-Biophysics repository on Zenodo.

Called by the central workflow .github/workflows/zenodo-release.yml.
Arguments: the files to upload (source archive of the tag first, then release assets).
Metadata come from .zenodo.json in the calling repository.

- First release of a repository: new Zenodo record (new DOI), placed in the SBE community.
- Later releases: new version of the same record (same "all versions" DOI).
  Earlier versions are found through the repository URL in related_identifiers.
- DRY_RUN=true: check everything and report what would happen, publish nothing.
"""
import datetime
import json
import os
import sys

import requests

COMMUNITY = "tum-sbe"
TOKEN = os.environ.get("ZENODO_TOKEN", "")
SANDBOX = os.environ.get("ZENODO_SANDBOX", "").strip().lower() == "true"
DRY_RUN = os.environ.get("DRY_RUN", "").strip().lower() == "true"
BASE = "https://sandbox.zenodo.org/api" if SANDBOX else "https://zenodo.org/api"
REPO = os.environ["GITHUB_REPOSITORY"]
REPO_URL = f"https://github.com/{REPO}"
NAME = REPO.split("/", 1)[1]
TAG = os.environ["TAG"]
FILES = sys.argv[1:]
H = {"Authorization": f"Bearer {TOKEN}"}
SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY", os.devnull)


def note(msg):
    print(msg)
    with open(SUMMARY, "a", encoding="utf-8") as s:
        s.write(msg + "\n")


def fail(msg):
    print(f"::error::{msg}")
    with open(SUMMARY, "a", encoding="utf-8") as s:
        s.write(f"**Error:** {msg}\n")
    sys.exit(1)


def call(method, url, **kw):
    r = requests.request(method, url, headers=H, timeout=300, **kw)
    if r.status_code >= 400:
        fail(f"Zenodo {method} {url} -> {r.status_code}: {r.text[:800]}")
    return r.json() if r.content else {}


# ---- metadata -------------------------------------------------------------
if not os.path.exists(".zenodo.json"):
    fail(".zenodo.json is missing. Copy it from Tum-Soil-Biophysics/project-template and fill it in.")
try:
    with open(".zenodo.json", encoding="utf-8") as fh:
        meta = json.load(fh)
except json.JSONDecodeError as e:
    fail(f".zenodo.json is not valid JSON (line {e.lineno}, column {e.colno}): {e.msg}. Check quotes and commas.")

PLACEHOLDERS = ("[Repository name]", "[short description]", "[Family name]", "[Given name]", "[What the code", "[keyword]")
if any(p in json.dumps(meta) for p in PLACEHOLDERS):
    fail(".zenodo.json still contains placeholders like [Family name]. Fill in title, creators, description and keywords.")
if not meta.get("creators"):
    fail(".zenodo.json needs at least one creator.")
for c in meta["creators"]:
    if "," not in c.get("name", ""):
        fail(f'Creator "{c.get("name", "")}" must be written as "Family name, Given name".')
if not meta.get("title") or not meta.get("description"):
    fail(".zenodo.json needs a title and a description.")

meta.setdefault("upload_type", "software")
meta.setdefault("access_right", "open")
meta["version"] = TAG
meta["publication_date"] = datetime.date.today().isoformat()
related = [r for r in meta.get("related_identifiers", []) if r.get("identifier") not in (REPO_URL, f"{REPO_URL}/tree/{TAG}")]
related += [
    {"identifier": REPO_URL, "relation": "isSupplementTo", "scheme": "url"},
    {"identifier": f"{REPO_URL}/tree/{TAG}", "relation": "isIdenticalTo", "scheme": "url"},
]
meta["related_identifiers"] = related
# Every record of the group goes into the SBE community.
comms = [c for c in meta.get("communities", []) if c.get("identifier") != COMMUNITY]
meta["communities"] = comms + [{"identifier": COMMUNITY}]
note(f"Metadata OK: \"{meta['title']}\", {len(meta['creators'])} creator(s), version {TAG}.")

if not TOKEN:
    if DRY_RUN:
        note("Dry run: the Zenodo token is not available here (private repository or missing secret). "
             "Metadata were checked; the Zenodo part runs once the repository is public.")
        sys.exit(0)
    fail("The secret ZENODO_TOKEN is missing (Organization settings > Secrets and variables > Actions).")

# ---- find an earlier version of this repository --------------------------
previous = None
page = 1
while previous is None:
    batch = call("GET", f"{BASE}/deposit/depositions", params={"size": 100, "page": page, "sort": "mostrecent"})
    for dep in batch:
        ids = [r.get("identifier") for r in dep.get("metadata", {}).get("related_identifiers", [])]
        if dep.get("submitted") and REPO_URL in ids:
            previous = dep
            break
    if len(batch) < 100:
        break
    page += 1

if DRY_RUN:
    files = ", ".join(os.path.basename(f) for f in FILES) or "none"
    if previous:
        note(f"Dry run: would create a NEW VERSION of record {previous['id']} (DOI {previous.get('doi', '?')}).")
    else:
        note(f"Dry run: would create a NEW RECORD with a new DOI in the community '{COMMUNITY}'.")
    note(f"Dry run: files that would be uploaded: {files}. Nothing was published.")
    sys.exit(0)

if not FILES:
    fail("No files to upload.")

# ---- create the draft -----------------------------------------------------
if previous:
    print(f"Earlier version found (record {previous['id']}); creating a new version.")
    meta.pop("communities", None)  # new versions inherit the communities of the first version
    nv = call("POST", f"{BASE}/deposit/depositions/{previous['id']}/actions/newversion")
    draft = call("GET", nv["links"]["latest_draft"])
    for f in draft.get("files", []):
        call("DELETE", f"{draft['links']['self']}/files/{f['id']}")
else:
    print("No earlier version found; creating a new record.")
    draft = call("POST", f"{BASE}/deposit/depositions", json={})

try:
    for path in FILES:
        print(f"Uploading {os.path.basename(path)} ({os.path.getsize(path) / 1e6:.1f} MB)")
        with open(path, "rb") as fh:
            call("PUT", f"{draft['links']['bucket']}/{os.path.basename(path)}", data=fh)
    call("PUT", draft["links"]["self"], json={"metadata": meta})
    done = call("POST", draft["links"]["publish"])
except SystemExit:
    requests.delete(draft["links"]["self"], headers=H, timeout=60)  # remove the unpublished draft
    raise

doi, concept = done["doi"], done.get("conceptdoi", "")
note(f"### Zenodo{' (sandbox)' if SANDBOX else ''}\n- This version: https://doi.org/{doi}\n- All versions: https://doi.org/{concept}")
with open(os.environ["GITHUB_OUTPUT"], "a") as out:
    out.write(f"doi={doi}\nconcept_doi={concept}\n")
