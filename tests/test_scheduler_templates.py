from pathlib import Path


def test_daily_and_weekly_launchd_templates_exist_and_reference_scripts():
    daily = Path("ops/launchd/com.ya-fundmind.daily.plist.template")
    weekly = Path("ops/launchd/com.ya-fundmind.weekly.plist.template")

    daily_text = daily.read_text(encoding="utf-8")
    weekly_text = weekly.read_text(encoding="utf-8")

    assert "WorkingDirectory" in daily_text
    assert "WorkingDirectory" in weekly_text
    assert "scripts/run_daily_ops.sh" in daily_text
    assert "scripts/run_weekly_ops.sh" in weekly_text
    assert "PROVIDER" in daily_text
    assert "PROVIDER" in weekly_text
    assert "ENABLE_MARKET_INTELLIGENCE" in daily_text
    assert "<string>false</string>" in daily_text
    assert "<integer>18</integer>" in daily_text
    assert "<integer>30</integer>" in daily_text
    assert "<key>Weekday</key>" in weekly_text
    assert "<integer>6</integer>" in weekly_text
    assert "<integer>10</integer>" in weekly_text


def test_daily_and_weekly_cron_templates_exist_and_reference_scripts():
    daily = Path("ops/cron/ya-fundmind.daily.crontab.template")
    weekly = Path("ops/cron/ya-fundmind.weekly.crontab.template")

    daily_text = daily.read_text(encoding="utf-8")
    weekly_text = weekly.read_text(encoding="utf-8")

    assert "scripts/run_daily_ops.sh" in daily_text
    assert "scripts/run_weekly_ops.sh" in weekly_text
    assert "30 18 * * *" in daily_text
    assert "0 10 * * 6" in weekly_text
    assert "YA_FUNDMIND_PROJECT_DIR" in daily_text
    assert "YA_FUNDMIND_PROJECT_DIR" in weekly_text
