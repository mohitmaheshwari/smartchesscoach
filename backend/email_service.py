"""
Email Notification Service for Chess Coach AI

Handles email notifications for:
1. New games analyzed
2. Weekly progress summaries
3. Recurring weakness detection alerts
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# SendGrid configuration
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@chesscoach.ai')
APP_NAME = "Chess Coach AI"


class EmailDeliveryError(Exception):
    """Custom exception for email delivery failures"""
    pass


def is_email_configured() -> bool:
    """Check if email service is properly configured"""
    return bool(SENDGRID_API_KEY and SENDER_EMAIL)


async def send_email(to: str, subject: str, html_content: str, plain_content: Optional[str] = None) -> bool:
    """
    Send email via SendGrid
    
    Args:
        to: Recipient email address
        subject: Email subject line
        html_content: HTML email content
        plain_content: Plain text fallback (optional)
    
    Returns:
        True if email sent successfully, False otherwise
    """
    if not is_email_configured():
        logger.warning("Email not configured. Skipping email send.")
        return False
    
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Content
        
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=to,
            subject=subject,
            html_content=html_content
        )
        
        if plain_content:
            message.add_content(Content("text/plain", plain_content))
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code == 202:
            logger.info(f"Email sent successfully to {to}")
            return True
        else:
            logger.warning(f"Email send returned status {response.status_code}")
            return False
            
    except ImportError:
        logger.error("SendGrid library not installed. Run: pip install sendgrid")
        return False
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


def generate_game_analyzed_email(
    user_name: str,
    games_count: int,
    platform: str,
    key_insights: List[str]
) -> tuple[str, str, str]:
    """
    Generate email content for new games analyzed notification
    
    Returns:
        Tuple of (subject, html_content, plain_content)
    """
    subject = f"🎯 {games_count} New Game{'s' if games_count > 1 else ''} Analyzed - {APP_NAME}"
    
    insights_html = ""
    insights_plain = ""
    if key_insights:
        insights_html = "<ul>" + "".join(f"<li>{insight}</li>" for insight in key_insights[:3]) + "</ul>"
        insights_plain = "\n".join(f"• {insight}" for insight in key_insights[:3])
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 30px; border-radius: 12px 12px 0 0; text-align: center; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 12px 12px; }}
            .highlight {{ background: #eef2ff; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #6366f1; }}
            .btn {{ display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; }}
            .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">♟️ {APP_NAME}</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">Your Personal Chess Coach</p>
            </div>
            <div class="content">
                <h2>Hey {user_name}! 👋</h2>
                <p>Great news! I've analyzed <strong>{games_count} new game{'s' if games_count > 1 else ''}</strong> from your {platform} account.</p>
                
                {f'''<div class="highlight">
                    <h3 style="margin-top: 0;">📊 Key Insights</h3>
                    {insights_html}
                </div>''' if insights_html else ''}
                
                <p>Head over to your Journey Dashboard to see the full analysis and track your progress.</p>
                
                <p style="text-align: center; margin-top: 30px;">
                    <a href="#" class="btn">View Your Journey →</a>
                </p>
                
                <p style="color: #6b7280; font-size: 14px; margin-top: 30px;">
                    Keep playing, keep improving! 🚀<br>
                    <em>— Your Chess Coach</em>
                </p>
            </div>
            <div class="footer">
                <p>You're receiving this because you enabled game sync notifications.</p>
                <p>To unsubscribe, update your settings in the app.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_content = f"""
{APP_NAME} - New Games Analyzed

Hey {user_name}!

Great news! I've analyzed {games_count} new game{'s' if games_count > 1 else ''} from your {platform} account.

{f"Key Insights:{chr(10)}{insights_plain}" if insights_plain else ""}

Head over to your Journey Dashboard to see the full analysis and track your progress.

Keep playing, keep improving!
— Your Chess Coach

---
You're receiving this because you enabled game sync notifications.
To unsubscribe, update your settings in the app.
    """
    
    return subject, html_content, plain_content


def generate_weekly_summary_email(
    user_name: str,
    games_analyzed: int,
    improvement_trend: str,
    top_weakness: Optional[str],
    top_strength: Optional[str],
    weekly_assessment: str
) -> tuple[str, str, str]:
    """
    Generate email content for weekly progress summary
    
    Returns:
        Tuple of (subject, html_content, plain_content)
    """
    trend_emoji = "📈" if improvement_trend == "improving" else "📊" if improvement_trend == "stable" else "💪"
    subject = f"{trend_emoji} Your Weekly Chess Progress - {APP_NAME}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 30px; border-radius: 12px 12px 0 0; text-align: center; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 12px 12px; }}
            .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
            .stat-box {{ background: white; padding: 20px; border-radius: 8px; text-align: center; flex: 1; margin: 0 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .stat-number {{ font-size: 32px; font-weight: bold; color: #6366f1; }}
            .stat-label {{ color: #6b7280; font-size: 14px; }}
            .assessment {{ background: #eef2ff; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #6366f1; }}
            .focus-area {{ background: #fef3c7; padding: 15px; border-radius: 8px; margin: 10px 0; }}
            .strength {{ background: #d1fae5; padding: 15px; border-radius: 8px; margin: 10px 0; }}
            .btn {{ display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; }}
            .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">♟️ Weekly Progress Report</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">{datetime.now(timezone.utc).strftime('%B %d, %Y')}</p>
            </div>
            <div class="content">
                <h2>Hey {user_name}! 👋</h2>
                
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-number">{games_analyzed}</div>
                        <div class="stat-label">Games Analyzed</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{trend_emoji}</div>
                        <div class="stat-label">{improvement_trend.title()}</div>
                    </div>
                </div>
                
                <div class="assessment">
                    <h3 style="margin-top: 0;">🎯 Coach's Assessment</h3>
                    <p>{weekly_assessment}</p>
                </div>
                
                {f'''<div class="focus-area">
                    <strong>⚠️ Focus Area:</strong> {top_weakness}
                </div>''' if top_weakness else ''}
                
                {f'''<div class="strength">
                    <strong>✨ Your Strength:</strong> {top_strength}
                </div>''' if top_strength else ''}
                
                <p style="text-align: center; margin-top: 30px;">
                    <a href="#" class="btn">View Full Report →</a>
                </p>
                
                <p style="color: #6b7280; font-size: 14px; margin-top: 30px;">
                    Keep up the great work! 🚀<br>
                    <em>— Your Chess Coach</em>
                </p>
            </div>
            <div class="footer">
                <p>You're receiving this weekly summary because you enabled email notifications.</p>
                <p>To unsubscribe, update your settings in the app.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_content = f"""
{APP_NAME} - Weekly Progress Report
{datetime.now(timezone.utc).strftime('%B %d, %Y')}

Hey {user_name}!

This Week's Stats:
• Games Analyzed: {games_analyzed}
• Trend: {improvement_trend.title()}

Coach's Assessment:
{weekly_assessment}

{f"Focus Area: {top_weakness}" if top_weakness else ""}
{f"Your Strength: {top_strength}" if top_strength else ""}

Keep up the great work!
— Your Chess Coach

---
You're receiving this weekly summary because you enabled email notifications.
To unsubscribe, update your settings in the app.
    """
    
    return subject, html_content, plain_content


def generate_weakness_alert_email(
    user_name: str,
    weakness_name: str,
    occurrence_count: int,
    advice: str
) -> tuple[str, str, str]:
    """
    Generate email content for recurring weakness detection alert
    
    Returns:
        Tuple of (subject, html_content, plain_content)
    """
    subject = f"⚠️ Pattern Detected: {weakness_name.title()} - {APP_NAME}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 30px; border-radius: 12px 12px 0 0; text-align: center; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 12px 12px; }}
            .alert-box {{ background: #fef3c7; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f59e0b; }}
            .advice-box {{ background: #eef2ff; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .btn {{ display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; }}
            .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">⚠️ Pattern Alert</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">Your coach noticed something</p>
            </div>
            <div class="content">
                <h2>Hey {user_name}! 👋</h2>
                
                <div class="alert-box">
                    <h3 style="margin-top: 0;">🔍 Recurring Pattern Detected</h3>
                    <p><strong>{weakness_name.title()}</strong> has appeared in <strong>{occurrence_count} recent games</strong>.</p>
                    <p>This is showing up often enough that it's worth focused practice.</p>
                </div>
                
                <div class="advice-box">
                    <h3 style="margin-top: 0;">💡 Coach's Advice</h3>
                    <p>{advice}</p>
                </div>
                
                <p>Remember: Awareness is the first step to improvement. Now that you know about this pattern, you can actively work on it!</p>
                
                <p style="text-align: center; margin-top: 30px;">
                    <a href="#" class="btn">Practice This Pattern →</a>
                </p>
                
                <p style="color: #6b7280; font-size: 14px; margin-top: 30px;">
                    You've got this! 💪<br>
                    <em>— Your Chess Coach</em>
                </p>
            </div>
            <div class="footer">
                <p>You're receiving this alert because you enabled weakness notifications.</p>
                <p>To unsubscribe, update your settings in the app.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_content = f"""
{APP_NAME} - Pattern Alert

Hey {user_name}!

Recurring Pattern Detected:
{weakness_name.title()} has appeared in {occurrence_count} recent games.
This is showing up often enough that it's worth focused practice.

Coach's Advice:
{advice}

Remember: Awareness is the first step to improvement. Now that you know about this pattern, you can actively work on it!

You've got this!
— Your Chess Coach

---
You're receiving this alert because you enabled weakness notifications.
To unsubscribe, update your settings in the app.
    """
    
    return subject, html_content, plain_content


async def send_game_analyzed_notification(
    user_email: str,
    user_name: str,
    games_count: int,
    platform: str,
    key_insights: List[str] = None
) -> bool:
    """Send notification when new games are analyzed"""
    if not user_email:
        return False
    
    subject, html_content, plain_content = generate_game_analyzed_email(
        user_name, games_count, platform, key_insights or []
    )
    
    return await send_email(user_email, subject, html_content, plain_content)


async def send_weekly_summary_notification(
    user_email: str,
    user_name: str,
    games_analyzed: int,
    improvement_trend: str,
    top_weakness: Optional[str],
    top_strength: Optional[str],
    weekly_assessment: str
) -> bool:
    """Send weekly progress summary email"""
    if not user_email:
        return False
    
    subject, html_content, plain_content = generate_weekly_summary_email(
        user_name, games_analyzed, improvement_trend, 
        top_weakness, top_strength, weekly_assessment
    )
    
    return await send_email(user_email, subject, html_content, plain_content)


async def send_weakness_alert_notification(
    user_email: str,
    user_name: str,
    weakness_name: str,
    occurrence_count: int,
    advice: str
) -> bool:
    """Send alert when a recurring weakness is detected"""
    if not user_email:
        return False
    
    subject, html_content, plain_content = generate_weakness_alert_email(
        user_name, weakness_name, occurrence_count, advice
    )
    
    return await send_email(user_email, subject, html_content, plain_content)
