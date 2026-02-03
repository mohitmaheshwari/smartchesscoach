"""
Test Email Notification Settings API Endpoints

Tests:
1. GET /api/settings/email-notifications - Get notification preferences (requires auth)
2. PUT /api/settings/email-notifications - Update notification preferences (requires auth)
3. POST /api/settings/test-email - Send test email (requires auth + SendGrid config)
4. Email service graceful handling of missing SendGrid API key
"""

import pytest
import requests
import os
import sys

# Add backend to path for importing email_service
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEmailNotificationEndpointsUnauthenticated:
    """Test email notification endpoints without authentication"""
    
    def test_get_email_settings_requires_auth(self):
        """GET /api/settings/email-notifications should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/settings/email-notifications")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print(f"✓ GET /api/settings/email-notifications returns 401 for unauthenticated requests")
    
    def test_put_email_settings_requires_auth(self):
        """PUT /api/settings/email-notifications should return 401 without auth"""
        payload = {
            "game_analyzed": True,
            "weekly_summary": True,
            "weakness_alert": False
        }
        response = requests.put(
            f"{BASE_URL}/api/settings/email-notifications",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print(f"✓ PUT /api/settings/email-notifications returns 401 for unauthenticated requests")
    
    def test_post_test_email_requires_auth(self):
        """POST /api/settings/test-email should return 401 without auth"""
        response = requests.post(f"{BASE_URL}/api/settings/test-email")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print(f"✓ POST /api/settings/test-email returns 401 for unauthenticated requests")


class TestEmailServiceConfiguration:
    """Test email service configuration and graceful handling"""
    
    def test_email_service_is_not_configured(self):
        """Email service should report not configured when SENDGRID_API_KEY is empty"""
        from email_service import is_email_configured
        
        # Since SENDGRID_API_KEY is empty in .env, this should return False
        result = is_email_configured()
        assert result == False, "Email should not be configured when SENDGRID_API_KEY is empty"
        print(f"✓ is_email_configured() returns False when SENDGRID_API_KEY is empty")
    
    def test_send_email_gracefully_fails_without_config(self):
        """send_email should return False gracefully when not configured"""
        import asyncio
        from email_service import send_email
        
        async def test_send():
            result = await send_email(
                to="test@example.com",
                subject="Test Subject",
                html_content="<p>Test content</p>"
            )
            return result
        
        result = asyncio.run(test_send())
        assert result == False, "send_email should return False when not configured"
        print(f"✓ send_email() returns False gracefully when SendGrid is not configured")
    
    def test_game_analyzed_notification_gracefully_fails(self):
        """send_game_analyzed_notification should return False when not configured"""
        import asyncio
        from email_service import send_game_analyzed_notification
        
        async def test_send():
            result = await send_game_analyzed_notification(
                user_email="test@example.com",
                user_name="Test User",
                games_count=3,
                platform="Chess.com",
                key_insights=["Good opening play", "Watch for pins"]
            )
            return result
        
        result = asyncio.run(test_send())
        assert result == False, "send_game_analyzed_notification should return False when not configured"
        print(f"✓ send_game_analyzed_notification() returns False gracefully when not configured")
    
    def test_weekly_summary_notification_gracefully_fails(self):
        """send_weekly_summary_notification should return False when not configured"""
        import asyncio
        from email_service import send_weekly_summary_notification
        
        async def test_send():
            result = await send_weekly_summary_notification(
                user_email="test@example.com",
                user_name="Test User",
                games_analyzed=10,
                improvement_trend="improving",
                top_weakness="pin blindness",
                top_strength="opening preparation",
                weekly_assessment="Great progress this week!"
            )
            return result
        
        result = asyncio.run(test_send())
        assert result == False, "send_weekly_summary_notification should return False when not configured"
        print(f"✓ send_weekly_summary_notification() returns False gracefully when not configured")
    
    def test_weakness_alert_notification_gracefully_fails(self):
        """send_weakness_alert_notification should return False when not configured"""
        import asyncio
        from email_service import send_weakness_alert_notification
        
        async def test_send():
            result = await send_weakness_alert_notification(
                user_email="test@example.com",
                user_name="Test User",
                weakness_name="pin blindness",
                occurrence_count=5,
                advice="Practice pin puzzles daily"
            )
            return result
        
        result = asyncio.run(test_send())
        assert result == False, "send_weakness_alert_notification should return False when not configured"
        print(f"✓ send_weakness_alert_notification() returns False gracefully when not configured")


class TestEmailTemplateGeneration:
    """Test email template generation functions"""
    
    def test_generate_game_analyzed_email(self):
        """Test game analyzed email template generation"""
        from email_service import generate_game_analyzed_email
        
        subject, html, plain = generate_game_analyzed_email(
            user_name="John",
            games_count=3,
            platform="Chess.com",
            key_insights=["Good opening", "Watch for pins"]
        )
        
        assert "3 New Games Analyzed" in subject
        assert "John" in html
        assert "Chess.com" in html
        assert "Good opening" in html
        assert "John" in plain
        print(f"✓ generate_game_analyzed_email() generates correct template")
    
    def test_generate_weekly_summary_email(self):
        """Test weekly summary email template generation"""
        from email_service import generate_weekly_summary_email
        
        subject, html, plain = generate_weekly_summary_email(
            user_name="Jane",
            games_analyzed=15,
            improvement_trend="improving",
            top_weakness="time management",
            top_strength="tactical awareness",
            weekly_assessment="Great progress this week!"
        )
        
        assert "Weekly" in subject
        assert "Jane" in html
        assert "15" in html
        assert "time management" in html
        assert "tactical awareness" in html
        assert "Jane" in plain
        print(f"✓ generate_weekly_summary_email() generates correct template")
    
    def test_generate_weakness_alert_email(self):
        """Test weakness alert email template generation"""
        from email_service import generate_weakness_alert_email
        
        subject, html, plain = generate_weakness_alert_email(
            user_name="Bob",
            weakness_name="pin blindness",
            occurrence_count=5,
            advice="Practice pin puzzles"
        )
        
        assert "Pattern Detected" in subject
        assert "Pin Blindness" in subject
        assert "Bob" in html
        assert "5 recent games" in html
        assert "Practice pin puzzles" in html
        assert "Bob" in plain
        print(f"✓ generate_weakness_alert_email() generates correct template")


class TestHealthAndBasicEndpoints:
    """Test basic endpoints are still working"""
    
    def test_health_endpoint(self):
        """Health endpoint should return healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ GET /api/health returns healthy status")
    
    def test_root_endpoint(self):
        """Root API endpoint should return message"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ GET /api/ returns correct message")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
