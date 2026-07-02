# Scoring/Risk Integration Draft

## Purpose

This draft describes how Phase 3 signal candidates might be reviewed before any future scoring or main-risk integration.

Current scope remains experimental:

- Do not change the main scoring model.
- Do not change the main risk logic.
- Do not change the daily default provider.
- Do not treat any output as a trading instruction.

## Signals That May Enter Future Scoring

These signals may be considered only after regression tests and manual review:

- `tiantian:*:return:*:total_return`
  - Direction hypothesis: higher recent return may be positive only when sample quality is normal.
  - Minimum sample: the window must satisfy `metadata.required_points`.
- `tiantian:*:drawdown:*:max_drawdown`
  - Direction hypothesis: smaller drawdown magnitude may be positive.
  - Minimum sample: same as the NAV window requirement.
- `tiantian:*:volatility:*:volatility`
  - Direction hypothesis: lower volatility may be positive for stable-allocation products.
  - Minimum sample: same as the NAV window requirement.
- `tiantian:*:liquidity:scale`
  - Direction hypothesis: larger scale may improve tradability and operating stability, but very large or very small products need separate rules.
- `tiantian:*:rating:rating`
  - Direction hypothesis: higher external rating may be positive only if source, freshness, and missing-value policy are documented.
- `akshare:*:return:*`
  - Direction hypothesis: recent return can be a candidate return factor only when source freshness is normal.
- `akshare:*:liquidity:*`
  - Direction hypothesis: scale can be a liquidity factor if units are normalized.
- `akshare:*:valuation:confidence`
  - Direction hypothesis: high confidence may allow stronger weighting of existing valuation evidence.

## Signals That May Enter Future Risk

These signals are more naturally risk gates or risk warnings:

- `*:provider:data_quality`
  - Fallback, stale cache, or critical provider warnings should reduce confidence before automated use.
- `tiantian:*:data_quality:*`
  - Degraded or warning windows should block use of NAV-derived scoring factors.
- `tiantian:*:drawdown:*:max_drawdown`
  - Large drawdown may become a risk issue after window and product-type thresholds are defined.
- `tiantian:*:volatility:*:volatility`
  - High volatility may become a risk issue after product-type thresholds are defined.

## Display-Only Signals

These fields should remain display-only unless a separately designed credibility model exists:

- `fund_manager`
- `fund_company`
- `inception_date`
- Provider endpoint timing
- Provider warning message text
- Raw CLI output

Display-only fields may help manual research, but they should not affect score or main `risk_issues` directly.

## Direction Assumptions

Initial assumptions must be treated as hypotheses, not production rules:

- Return: higher can be positive, but only after drawdown and volatility context.
- Drawdown: lower magnitude is generally positive.
- Volatility: lower is generally positive for broad index and allocation products, but not universally.
- Scale: moderate-to-large scale may be positive for liquidity; outliers require caps.
- Rating: higher may be positive only if source quality is stable.
- Data quality: degraded data should block automated use; warning data should require explicit partial-sample handling.

## Minimum Sample Requirements

NAV window signals must follow `docs/contracts/scoring-risk-input-contract.md`:

- `1m`: at least 20 valid NAV points.
- `3m`: at least 60 valid NAV points.
- `6m`: at least 120 valid NAV points.
- `1y`: at least 240 valid NAV points.
- `all`: display context unless a minimum comparable window is also satisfied.

For any scoring or risk use:

- `metadata.window_mode` must be `nav_points`.
- `metadata.actual_points >= metadata.required_points`.
- `data_quality_grade` must be `normal`.
- `metadata.annualized_return_unstable` must not be true for annualized return factors.

## Missing Field Handling

Missing fields must never improve a score or suppress a risk:

- Missing NAV value: exclude the specific NAV factor.
- Missing scale/rating: exclude that detail factor.
- Missing manager/company/inception date: display as missing only.
- Missing provider health: treat as unknown data quality, not as normal.

## Stale Cache Handling

Stale cache data should not silently enter scoring or main risk:

- Stale records must remain visible in provider warnings or freshness metadata.
- Future scoring should either exclude stale-derived factors or apply a documented confidence penalty.
- Future risk should surface stale data as a data-quality issue when automated decisions depend on it.

## Degraded And Warning Data

- `degraded`: exclude from scoring and main risk logic.
- `warning`: exclude by default unless a future model explicitly supports partial samples.
- `critical` provider warnings: require manual review before automated downstream use.

## Required Regression Tests

Before changing the main model, add tests for:

- Existing fixture/AKShare daily scores stay stable unless intentionally changed.
- Missing Tiantian fields never improve a score.
- Stale Tiantian cache never improves a score or hides risk.
- Degraded NAV windows are excluded from all model inputs.
- Warning NAV windows are excluded unless explicitly allowed.
- Short-sample annualized return is excluded.
- Provider fallback changes data-quality confidence predictably.
- Snapshot deltas show expected score and risk changes.
- JSON contract validation continues passing.
- Markdown/HTML wording does not become a downstream data dependency.

## Why This Phase Does Not Integrate The Main Model

The candidate layer still needs historical stability evidence, clearer thresholds, and baseline comparisons. Moving these signals directly into score or main risk now would change user-facing conclusions without enough regression evidence.

The current phase therefore produces only:

- `signal_candidates.json`
- `signal_stability_report.json`
- `signal_candidates_explained.md`
- Optional snapshot `signal_quality_summary`

These files are research aids, not model outputs.
