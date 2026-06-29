from pathlib import Path


def test_daily_ops_script_wraps_expected_commands():
    script = Path("scripts/run_daily_ops.sh").read_text(encoding="utf-8")

    assert "daily-research" in script
    assert "weekly-research" in script
    assert "generate-evidence-dashboard" in script
    assert "evaluate-long-horizon-stability" in script
    assert "ops-status" in script
    assert "latest_summary.md" in script


def test_launchd_and_cron_templates_exist_and_reference_script():
    launchd = Path("ops/launchd/com.ya-fundmind.daily.plist.template").read_text(encoding="utf-8")
    cron = Path("ops/cron/ya-fundmind.crontab.template").read_text(encoding="utf-8")

    assert "scripts/run_daily_ops.sh" in launchd
    assert "scripts/run_daily_ops.sh" in cron
    assert "PYTHON_BIN" in launchd
    assert "YA_FUNDMIND_PROJECT_DIR" in cron
