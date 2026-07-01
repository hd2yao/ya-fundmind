from pathlib import Path


def test_launchd_scheduler_scripts_exist_and_support_required_flags():
    install = Path("scripts/install_launchd_scheduler.sh")
    uninstall = Path("scripts/uninstall_launchd_scheduler.sh")
    status = Path("scripts/status_launchd_scheduler.sh")

    install_text = install.read_text(encoding="utf-8")
    uninstall_text = uninstall.read_text(encoding="utf-8")
    status_text = status.read_text(encoding="utf-8")

    assert "--daily" in install_text
    assert "--weekly" in install_text
    assert "--dry-run" in install_text
    assert "PROVIDER" in install_text
    assert "launchctl bootstrap" in install_text
    assert "plutil" in install_text
    assert "chmod +x" in install_text
    assert "--daily" in uninstall_text
    assert "--weekly" in uninstall_text
    assert "launchctl bootout" in uninstall_text
    assert "保留日志和 outputs" in uninstall_text
    assert "daily 是否已安装" in status_text
    assert "weekly 是否已安装" in status_text
    assert "ops-status" in status_text


def test_ops_runner_scripts_write_logs_and_keep_expected_steps():
    daily = Path("scripts/run_daily_ops.sh").read_text(encoding="utf-8")
    weekly = Path("scripts/run_weekly_ops.sh").read_text(encoding="utf-8")

    assert "outputs/logs/daily-ops-" in daily
    assert "REFRESH_DASHBOARD" in daily
    assert "latest_summary.json" in daily
    assert "daily-research" in daily
    assert "weekly-research" in daily
    assert "evaluate-long-horizon-stability" in daily
    assert "ops-status" in daily

    assert "outputs/logs/weekly-ops-" in weekly
    assert "weekly-research" in weekly
    assert "generate-evidence-dashboard" in weekly
    assert "evaluate-long-horizon-stability" in weekly
    assert "ops-status" in weekly
