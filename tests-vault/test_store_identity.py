"""Vault-side regression tests for project identity in the central store.

The store is keyed by slug, and the slug comes from `kuraka.config.yaml`
`project.name` (else the folder name). Two ways that produced a SPLIT store —
the same directory owning two entries, with its history divided between them:

  1. the solution was renamed (`plugginsqlagent` → `dbcanvas`, 2026-08);
  2. the config scan matched an indented `name:` inside a folded block, yielding
     the slug `parplus-src-package-json-2-appparplus-slugified` next to `parplus`.

(2) is fixed at the source (`_plausible_project_name`); (1) cannot be — renaming
is legitimate — so `kuraka-discover.py` reports it and `kuraka-merge-project.py`
fuses the two entries.

Run from the vault root:  python3 -m pytest tests-vault/ -v
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VAULT))

import kuraka_common as kc  # noqa: E402


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, VAULT / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


discover = _load("kuraka_discover", "kuraka-discover.py")


# --- 1. slug derivation -------------------------------------------------------

def test_config_name_wins_over_folder_name(tmp_path):
    proj = tmp_path / "PlugginSQLAgent"
    proj.mkdir()
    (proj / "kuraka.config.yaml").write_text(
        "project:\n  name: dbcanvas\n  description: whatever\n", encoding="utf-8")
    assert kc.project_slug(proj) == "dbcanvas"


def test_folded_description_cannot_hijack_the_slug(tmp_path):
    """The real parplus config: a `description: |` block whose lines mention a
    path. The old scan took the first indented `name:` it saw."""
    proj = tmp_path / "Parplus"
    proj.mkdir()
    (proj / "kuraka.config.yaml").write_text(
        "project:\n"
        "  description: |\n"
        "    Angular app. Package metadata:\n"
        "      name: src/package.json 2 app.parplus\n"
        "  stack: typescript\n",
        encoding="utf-8")
    assert kc.project_slug(proj) == "parplus"  # folder name, not the garbage


def test_implausible_config_names_fall_back_to_the_folder(tmp_path):
    proj = tmp_path / "mi-proyecto"
    proj.mkdir()
    for bad in ("src/package.json", "|", "una frase larguisima con demasiadas palabras sueltas"):
        (proj / "kuraka.config.yaml").write_text(
            f"project:\n  name: {bad}\n", encoding="utf-8")
        assert kc.project_slug(proj) == "mi-proyecto", bad


def test_explicit_override_always_wins(tmp_path):
    proj = tmp_path / "carpeta"
    proj.mkdir()
    (proj / "kuraka.config.yaml").write_text("project:\n  name: otro\n", encoding="utf-8")
    assert kc.project_slug(proj, "Elegido") == "elegido"


# --- 2. split-store detection -------------------------------------------------

def test_discover_reports_one_path_registered_under_two_slugs(tmp_path):
    vault = tmp_path / "vault"
    for slug in ("viejo", "nuevo"):
        d = vault / "projects" / slug
        d.mkdir(parents=True)
        (d / "registry.md").write_text(
            f"---\nname: {slug}\npath: /tmp/mismo-proyecto\n---\n", encoding="utf-8")
    dupes = {p: s for p, s in discover.registry_slugs(vault).items() if len(s) > 1}
    assert len(dupes) == 1
    assert sorted(next(iter(dupes.values()))) == ["nuevo", "viejo"]


def test_discover_marker_recognises_non_claude_mounts(tmp_path):
    """An Antigravity-only project used to read as 'registered but NOT mounted'."""
    for platform, marker in ((".agents", "po-analyst.md"), (".codex", "po-analyst.toml")):
        proj = tmp_path / platform.lstrip(".")
        (proj / platform / "agents").mkdir(parents=True)
        (proj / platform / "agents" / marker).write_text("x", encoding="utf-8")
    found = discover.find_mounts([tmp_path], 4)
    assert len(found) == 2


# --- 3. merging two entries of the same project -------------------------------

def _store(vault: Path, slug: str, path: str) -> Path:
    d = vault / "projects" / slug
    (d / "state").mkdir(parents=True)
    (d / "registry.md").write_text(
        f"---\nname: {slug}\npath: {path}\n---\n\n# {slug}\n", encoding="utf-8")
    return d


def _merge(vault: Path, src: str, dst: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VAULT / "kuraka-merge-project.py"), src, dst,
         "--vault", str(vault), "--yes", *extra],
        capture_output=True, text=True)


def test_merge_moves_history_and_records_the_alias(tmp_path):
    vault = tmp_path / "vault"
    old = _store(vault, "viejo", "/tmp/p")
    new = _store(vault, "nuevo", "/tmp/p")
    (old / "state" / "REQ-1.md").write_text("historia vieja\n", encoding="utf-8")
    (old / "backup.yaml").write_text(
        "project: viejo\nlast_backup: 2026-07-01\nlast_branch: a\nbranches:\n  - a\n",
        encoding="utf-8")
    (new / "state" / "REQ-2.md").write_text("historia nueva\n", encoding="utf-8")
    (new / "backup.yaml").write_text(
        "project: nuevo\nlast_backup: 2026-08-01\nlast_branch: b\nbranches:\n  - b\n",
        encoding="utf-8")

    r = _merge(vault, "viejo", "nuevo")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (new / "state" / "REQ-1.md").read_text() == "historia vieja\n"
    assert (new / "state" / "REQ-2.md").is_file()
    assert not old.exists()
    reg = (new / "registry.md").read_text()
    assert "aliases: [viejo]" in reg and "Historial de nombres" in reg
    side = (new / "backup.yaml").read_text()
    assert "last_backup: 2026-08-01" in side       # the later date wins
    assert "- a" in side and "- b" in side          # branches are unioned


def test_merge_never_clobbers_the_target_on_conflict(tmp_path):
    vault = tmp_path / "vault"
    old = _store(vault, "viejo", "/tmp/p")
    new = _store(vault, "nuevo", "/tmp/p")
    (old / "state" / "shared.md").write_text("version vieja\n", encoding="utf-8")
    (new / "state" / "shared.md").write_text("version nueva\n", encoding="utf-8")

    r = _merge(vault, "viejo", "nuevo")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (new / "state" / "shared.md").read_text() == "version nueva\n"
    assert "conflicto" in r.stdout


def test_merge_dry_run_writes_nothing(tmp_path):
    vault = tmp_path / "vault"
    old = _store(vault, "viejo", "/tmp/p")
    _store(vault, "nuevo", "/tmp/p")
    (old / "state" / "REQ-1.md").write_text("x\n", encoding="utf-8")

    r = _merge(vault, "viejo", "nuevo", "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert old.exists()
    assert not (vault / "projects" / "nuevo" / "state" / "REQ-1.md").exists()


# --- 4. adoption artifacts are drafted, never imposed --------------------------

def _adopt(project: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VAULT / "kuraka-init.py"), "--target", str(project),
         "--adopt", "--yes", *extra],
        capture_output=True, text=True)


def test_adopt_drafts_config_and_layer_skeleton(tmp_path):
    """Mounting used to only PRINT how to create these, so a project adopted with
    mount-kuraka ran with no config at all and its docs/process mapping drifted."""
    proj = tmp_path / "app"
    proj.mkdir()
    (proj / "package.json").write_text('{"name":"app"}', encoding="utf-8")

    r = _adopt(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    cfg = (proj / "kuraka.config.yaml").read_text()
    assert "schema_version: 1" in cfg
    assert "name: app" in cfg                       # slug = folder name
    assert "docs_process_root: docs/process/" in cfg  # the mapping the agents read
    for d in ("conventions", "lessons-learned", "review-checks", "agents"):
        assert (proj / ".claude" / "project" / d).is_dir()


def test_adopt_never_overwrites_an_existing_config(tmp_path):
    proj = tmp_path / "app"
    (proj / ".claude" / "project" / "conventions").mkdir(parents=True)
    (proj / "kuraka.config.yaml").write_text("mío\n", encoding="utf-8")
    r = _adopt(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (proj / "kuraka.config.yaml").read_text() == "mío\n"


def test_adopt_honours_the_platform_layer_root(tmp_path):
    proj = tmp_path / "app"
    proj.mkdir()
    r = _adopt(proj, "--layer-root", ".agents/project")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (proj / ".agents" / "project" / "conventions").is_dir()
    assert not (proj / ".claude" / "project").exists()


# --- 5. the slug-drift guard ---------------------------------------------------

def test_registered_slug_wins_over_a_renamed_config(tmp_path):
    """A project registered as X whose config later says Y must keep backing up
    into X — otherwise its history is stranded (guai-home-marketplace, 62 ciclos,
    vs the `guaihome-marketplace` its config had been given)."""
    vault = tmp_path / "vault"
    proj = tmp_path / "app"
    proj.mkdir()
    d = vault / "projects" / "nombre-viejo"
    d.mkdir(parents=True)
    (d / "registry.md").write_text(
        f"---\nname: nombre-viejo\npath: {proj}\n---\n", encoding="utf-8")
    (proj / "kuraka.config.yaml").write_text(
        "project:\n  name: nombre-nuevo\n", encoding="utf-8")

    assert kc.project_slug(proj) == "nombre-nuevo"
    assert kc.registered_slug_for_path(vault, proj) == "nombre-viejo"

    r = subprocess.run(
        [sys.executable, str(VAULT / "kuraka-backup.py"), str(proj),
         "--vault", str(vault), "--overrides-only"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "nombre-viejo" in r.stdout          # backed up under the registered slug
    assert "ya está registrado" in r.stderr    # and said so
    assert not (vault / "projects" / "nombre-nuevo").exists()


def test_explicit_name_still_overrides_the_guard(tmp_path):
    vault = tmp_path / "vault"
    proj = tmp_path / "app"
    proj.mkdir()
    d = vault / "projects" / "viejo"
    d.mkdir(parents=True)
    (d / "registry.md").write_text(f"---\nname: viejo\npath: {proj}\n---\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(VAULT / "kuraka-backup.py"), str(proj), "--vault", str(vault),
         "--name", "elegido", "--overrides-only"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "elegido" in r.stdout


def test_merge_of_different_paths_needs_confirmation(tmp_path):
    """Not a rename: two entries pointing at DIFFERENT directories."""
    vault = tmp_path / "vault"
    _store(vault, "uno", "/tmp/a")
    _store(vault, "dos", "/tmp/b")
    r = subprocess.run(
        [sys.executable, str(VAULT / "kuraka-merge-project.py"), "uno", "dos",
         "--vault", str(vault)],
        capture_output=True, text=True, input="")
    assert "no parece un rename" in r.stdout
    assert (vault / "projects" / "uno").exists()  # nothing happened
