#!/usr/bin/env python3
"""Safe, research-only runner for the BIE H140 or H139 repository ZIP.
Never authenticates to a brokerage or submits orders.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
ZIPS = ("BIE_H140_REAL_MARKET_ROBUSTNESS_CODEX_20261017.zip", "BIE_H139_OPTIMIZED_CODEX_CORE_UNDER_25MB.zip")
MAX_TOTAL_UNCOMPRESSED = 250 * 1024 * 1024


def unpack(archive: Path, dest: Path) -> tuple[Path, str]:
    if not archive.is_file():
        raise FileNotFoundError(f"Missing archive: {archive.name}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError("ZIP archive integrity failed")
        total = 0
        for item in z.infolist():
            part = PurePosixPath(item.filename.replace('\\', '/'))
            if (part.is_absolute() or '..' in part.parts or not part.parts
                    or ':' in part.parts[0] or (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError(f"Unsafe ZIP entry: {item.filename!r}")
            total += item.file_size
            if total > MAX_TOTAL_UNCOMPRESSED:
                raise ValueError("ZIP uncompressed size exceeds safe limit")
        # Extract into a fresh directory only. Never overwrite user's working files.
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        z.extractall(dest)
    matches = [p.parent for p in dest.rglob('__main__.py')
               if p.parent.name == 'bie' and (p.parent.parent / 'tests').is_dir()]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one BIE project root, found {len(matches)}")
    project = matches[0].parent
    return project, digest


def run(project: Path, args: list[str]) -> bool:
    print('>', sys.executable, *args, flush=True)
    try:
        proc = subprocess.run([sys.executable, *args], cwd=project, check=False, timeout=120)
    except subprocess.TimeoutExpired:
        print('TIMEOUT: command exceeded 120 seconds. Not counted as a pass.', flush=True)
        return False
    if proc.returncode:
        print(f'FAIL: exit status {proc.returncode}', flush=True)
    return proc.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description='BIE offline research verification; no orders or brokerage access')
    ap.add_argument('--archive', type=Path, help='Optional ZIP path (default: H140, otherwise H139)')
    ap.add_argument('--full-tests', action='store_true', help='Run inherited full test suite (may be slow)')
    ap.add_argument('--no-demo', action='store_true', help='Do not generate synthetic demo')
    a = ap.parse_args()
    archive = a.archive or next((ROOT / name for name in ZIPS if (ROOT / name).exists()), ROOT / ZIPS[0])
    try:
        project, digest = unpack(archive.resolve(), ROOT / '.bie_runtime' / 'extracted')
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        print(f'Cannot start: {e}', file=sys.stderr)
        return 2
    print(f'ARCHIVE: {archive.name}\nSHA256: {digest}\nPROJECT: {project}', flush=True)
    print('RESEARCH-ONLY: no credentials, broker connection, real trades, or funding.\n', flush=True)
    tests = [f'tests.{p.stem}' for p in sorted((project / 'tests').glob('test_*h140*.py'))]
    if (project / 'tests' / 'test_flood_movement_h139.py').exists():
        tests.insert(0, 'tests.test_flood_movement_h139')
    if not tests:
        print('No H139/H140 research tests found. Cannot certify execution.')
        return 3
    ok = run(project, ['-m', 'unittest', *tests, '-q'])
    vendor = project / 'vendor' / 'desktop_v1' / 'ORIGINAL_BIE_V8_UNMODIFIED.zip'
    if vendor.is_file():
        ok = run(project, ['-m', 'bie', 'verify-vendor']) and ok
    else:
        print('NOTICE: old vendor ZIP excluded from lean package. Full vendor verification NOT performed.')
    if a.full_tests:
        ok = run(project, ['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-q']) and ok
    if not a.no_demo:
        folder = project / 'reports'
        folder.mkdir(exist_ok=True)
        out = folder / 'H140_REPO_RUNNER_SYNTHETIC.json'
        if out.exists():
            out.unlink()
        ok = run(project, ['-m', 'bie', 'flood-h139-demo', '--world', 'flow',
                           '--seed', '7123', '--report', str(out)]) and ok
        if out.exists():
            data = json.loads(out.read_text())
            print('DEMO CREATED:', out, '\nSource mode:', data.get('source_mode'),
                  '\nActual orders: 0 (offline research command)', flush=True)
    print('\nRESULT:', 'PASS (targeted research execution only)' if ok else 'FAIL / incomplete')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
