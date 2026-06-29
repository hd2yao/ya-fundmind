from fund_agent.signal_review import render_signal_promotion_proposal


def test_promotion_proposal_markdown_defaults_to_no_main_model():
    review = {
        "review_items": [
            {
                "signal_id": "tiantian:510300:return:1m:total_return",
                "recommended_status": "approved_for_experiment",
                "direction_hypothesis": "positive",
                "evidence": ["eligible_rate=0.9"],
                "metadata": {"min_required_points": 20},
            },
            {
                "signal_id": "tiantian:510300:return:3m:warning",
                "recommended_status": "needs_data",
                "direction_hypothesis": "positive",
                "evidence": ["warning_data_blocked"],
                "metadata": {"min_required_points": 60},
            },
        ],
        "summary": {"total_review_items": 2},
    }

    markdown = render_signal_promotion_proposal(review)

    assert "当前没有直接修改主模型" in markdown
    assert "是否建议进入主模型：no" in markdown
    assert "approved_for_experiment" in markdown
    assert "needs_data" in markdown
