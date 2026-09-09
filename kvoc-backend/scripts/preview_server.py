"""Dev server for the Browser-pane preview (see ../../.claude/launch.json).

Runs against a throwaway scratch database (`kvoc-backend/_preview.db`,
already covered by `.gitignore`'s `*.db`), never the real
`kvoc-backend/kvoc.db` - so poking around in the browser (registering test
accounts, buying a meat share, generating a gift voucher) never touches
real data. Delete `_preview.db` any time to start over with an empty one.

Not needed for normal development - `python run.py` from `kvoc-backend/`
already does the right thing there, using the real `kvoc.db`. This exists
only because a Browser-pane launch config can't set environment variables
or a working directory of its own (see `.claude/launch.json`'s "url" note),
so it needs a tiny wrapper that does both itself, robust to whatever
directory the harness actually launches it from.
"""
import os
import runpy
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
os.chdir(_BACKEND_ROOT)
sys.path.insert(0, _BACKEND_ROOT)

os.environ["KVOC_DATABASE_URL"] = "sqlite:///" + os.path.join(_BACKEND_ROOT, "_preview.db").replace("\\", "/")
os.environ.setdefault("KVOC_JWT_SECRET", "preview-only-not-a-real-secret")
os.environ.setdefault("KVOC_ADMIN_TOKEN", "preview-only-not-a-real-secret")

runpy.run_path(os.path.join(_BACKEND_ROOT, "run.py"), run_name="__main__")
