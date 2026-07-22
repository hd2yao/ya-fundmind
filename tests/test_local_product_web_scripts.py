from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_launchd_template_is_loopback_only_and_persistent() -> None:
    template = (ROOT / "ops" / "launchd" / "com.ya-fundmind.web.plist.template").read_text(
        encoding="utf-8"
    )

    assert "com.ya-fundmind.web" in template
    assert "product-web" in template
    assert "127.0.0.1" in template
    assert "8768" in template
    assert "0.0.0.0" not in template
    assert "<key>RunAtLoad</key>" in template
    assert "<key>KeepAlive</key>" in template
    assert "product-web.out.log" in template
    assert "product-web.err.log" in template


def test_install_script_dry_run_renders_valid_web_plist(tmp_path: Path) -> None:
    output_dir = tmp_path / "runtime"
    env = {
        **os.environ,
        "YA_FUNDMIND_PROJECT_DIR": str(ROOT),
        "OUTPUT_DIR": str(output_dir),
        "PYTHON_BIN": str(ROOT / ".venv" / "bin" / "python"),
        "HOME": str(tmp_path / "home"),
    }

    result = subprocess.run(
        ["bash", "scripts/install_local_product_web.sh", "--dry-run"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    preview = output_dir / "logs" / "com.ya-fundmind.web.plist.preview"
    assert result.returncode == 0, result.stderr
    assert preview.is_file()
    payload = plistlib.loads(preview.read_bytes())
    assert payload["Label"] == "com.ya-fundmind.web"
    assert payload["ProgramArguments"][0] == str(ROOT / ".venv" / "bin" / "python")
    assert payload["ProgramArguments"][-4:] == ["--host", "127.0.0.1", "--port", "8768"]
    assert payload["WorkingDirectory"] == str(ROOT)
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True
    assert payload["StandardOutPath"] == str(output_dir / "logs" / "product-web.out.log")


def test_web_service_scripts_do_not_touch_daily_or_weekly_scheduler() -> None:
    uninstall = (ROOT / "scripts" / "uninstall_local_product_web.sh").read_text(encoding="utf-8")
    install = (ROOT / "scripts" / "install_local_product_web.sh").read_text(encoding="utf-8")

    assert "com.ya-fundmind.web" in uninstall
    assert "com.ya-fundmind.daily" not in uninstall
    assert "com.ya-fundmind.weekly" not in uninstall
    assert "run_daily_ops" not in install
    assert "run_weekly_ops" not in install


def test_deploy_and_status_scripts_cover_build_health_and_logs() -> None:
    deploy = (ROOT / "scripts" / "deploy_local_product_web.sh").read_text(encoding="utf-8")
    status = (ROOT / "scripts" / "status_local_product_web.sh").read_text(encoding="utf-8")

    assert "npm ci" in deploy
    assert "npm run typecheck" in deploy
    assert "npm test -- --run" in deploy
    assert "npm run build" in deploy
    assert "product-web" in deploy
    assert "launchctl kickstart" in deploy
    assert "/api/health" in status
    assert "http://127.0.0.1:8768" in status
    assert "product-web.out.log" in status
    assert "product-web.err.log" in status
