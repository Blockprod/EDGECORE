#!/usr/bin/env python
"""Validation test for T0.2: Slack Webhook Configuration"""

from monitoring.slack_alerter import SlackAlerter

def test_t0_2():
    print("\n=== T0.2 VALIDATION: Slack Webhook Configuration ===\n")
    
    # Step 1: Check .env.example has SLACK_WEBHOOK_URL template
    env_example_path = ".env.example"
    with open(env_example_path, 'r') as f:
        env_content = f.read()
    
    assert "SLACK_WEBHOOK_URL" in env_content
    print("[OK] .env.example contains SLACK_WEBHOOK_URL template")
    
    assert "EMAIL_SMTP_SERVER" in env_content
    print("[OK] .env.example contains EMAIL alerting config")
    
    # Step 2: Test SlackAlerter logs warning when webhook not configured
    print("\n[TEST] Creating SlackAlerter with webhook_url=None...")
    alerter_disabled = SlackAlerter(webhook_url=None)
    assert not alerter_disabled.enabled
    print("[OK] SlackAlerter correctly disabled when url is None")
    
    # Step 3: Test SlackAlerter enabled when webhook provided
    test_webhook = "https://hooks.slack.com/services/TEST/TEST/TEST"
    alerter_enabled = SlackAlerter(webhook_url=test_webhook)
    assert alerter_enabled.enabled
    print("[OK] SlackAlerter enabled when webhook_url provided")
    
    # Step 4: Verify webhook URL stored correctly
    assert alerter_enabled.webhook_url == test_webhook
    print("[OK] Webhook URL stored correctly")
    
    print("\n[PASS] T0.2 Validation Successful\n")


if __name__ == "__main__":
    try:
        test_t0_2()
    except Exception as e:
        print(f"\n[FAIL] T0.2 Validation Failed: {e}\n")
        import traceback
        traceback.print_exc()
        raise
