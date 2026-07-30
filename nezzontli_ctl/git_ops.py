"""Operaciones git reales (no la API REST de ningún host — así las fotos
pasan por el filtro de git-lfs como cualquier commit hecho a mano)."""

import subprocess

from nezzontli_ctl.config import REPO_ROOT


def _git(*args, check=True):
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=check, capture_output=True, text=True
    )


def stage(paths):
    _git("add", *[str(p) for p in paths])


def diff_stat_cached():
    result = _git("diff", "--cached", "--stat")
    return result.stdout


def commit_and_push(message):
    commit = _git("commit", "-m", message, check=False)
    if commit.returncode != 0:
        return False, (commit.stdout or "") + (commit.stderr or "")

    push = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    ok = push.returncode == 0
    output = (push.stdout or "") + (push.stderr or "")
    return ok, output
