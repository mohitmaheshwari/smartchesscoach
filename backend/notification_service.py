"""
Notification Service - In-App and Browser Push Notifications

Handles:
- In-app notification storage and retrieval
- Browser push notification triggers
- Notification preferences
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    GAME_ANALYZED = "game_analyzed"
    NEW_MILESTONE = "new_milestone"
    FOCUS_UPDATED = "focus_updated"
    WEEKLY_SUMMARY = "weekly_summary"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


async def create_notification(
    db,
    user_id: str,
    notification_type: NotificationType,
    title: str,
    message: str,
    data: Dict = None,
    priority: NotificationPriority = NotificationPriority.MEDIUM,
    action_url: str = None
) -> Dict:
    """
    Create a new notification for a user.
    
    Returns the created notification document.
    """
    notification = {
        "user_id": user_id,
        "type": notification_type.value,
        "title": title,
        "message": message,
        "data": data or {},
        "priority": priority.value,
        "action_url": action_url,
        "read": False,
        "dismissed": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    result = await db.notifications.insert_one(notification)
    notification["id"] = str(result.inserted_id)
    del notification["_id"] if "_id" in notification else None
    
    logger.info(f"Created notification for user {user_id}: {title}")
    return notification


async def get_user_notifications(
    db,
    user_id: str,
    unread_only: bool = False,
    limit: int = 20
) -> List[Dict]:
    """
    Get notifications for a user.
    """
    query = {"user_id": user_id, "dismissed": False}
    if unread_only:
        query["read"] = False
    
    notifications = await db.notifications.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return notifications


async def get_unread_count(db, user_id: str) -> int:
    """Get count of unread notifications."""
    return await db.notifications.count_documents({
        "user_id": user_id,
        "read": False,
        "dismissed": False
    })


async def mark_notification_read(db, user_id: str, notification_id: str = None) -> bool:
    """
    Mark notification(s) as read.
    If notification_id is None, marks all as read.
    """
    from bson import ObjectId
    
    if notification_id:
        result = await db.notifications.update_one(
            {"_id": ObjectId(notification_id), "user_id": user_id},
            {"$set": {"read": True}}
        )
        return result.modified_count > 0
    else:
        result = await db.notifications.update_many(
            {"user_id": user_id, "read": False},
            {"$set": {"read": True}}
        )
        return result.modified_count > 0


async def dismiss_notification(db, user_id: str, notification_id: str) -> bool:
    """Dismiss a notification (soft delete)."""
    from bson import ObjectId
    
    result = await db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": user_id},
        {"$set": {"dismissed": True}}
    )
    return result.modified_count > 0


async def notify_game_analyzed(
    db,
    user_id: str,
    game_id: str,
    notification_message: str,
    game_result: str = None
) -> Dict:
    """
    Create notification for a newly analyzed game.
    """
    # Determine icon based on result
    icon = "trophy" if game_result == "Win" else "target" if game_result == "Loss" else "zap"
    
    return await create_notification(
        db=db,
        user_id=user_id,
        notification_type=NotificationType.GAME_ANALYZED,
        title="Game Analyzed",
        message=notification_message,
        data={
            "game_id": game_id,
            "icon": icon,
            "result": game_result
        },
        priority=NotificationPriority.HIGH,
        action_url=f"/game/{game_id}"
    )


async def notify_focus_updated(
    db,
    user_id: str,
    new_weakness: str,
    previous_weakness: str = None
) -> Dict:
    """
    Create notification when focus area changes.
    """
    if previous_weakness and previous_weakness != new_weakness:
        message = f"Your focus shifted from '{previous_weakness}' to '{new_weakness}'"
    else:
        message = f"Focus area identified: {new_weakness}"
    
    return await create_notification(
        db=db,
        user_id=user_id,
        notification_type=NotificationType.FOCUS_UPDATED,
        title="Focus Updated",
        message=message,
        data={
            "new_weakness": new_weakness,
            "previous_weakness": previous_weakness
        },
        priority=NotificationPriority.MEDIUM,
        action_url="/focus"
    )


# Browser Push Notification Support
# This returns data that frontend can use to trigger browser notifications

def get_push_notification_payload(notification: Dict) -> Dict:
    """
    Format notification for browser push API.
    Frontend should request this and use the Notification API.
    """
    return {
        "title": notification.get("title", "Chess Coach"),
        "body": notification.get("message", ""),
        "icon": "/logo192.png",  # App icon
        "badge": "/badge.png",
        "tag": notification.get("type", "general"),
        "data": {
            "url": notification.get("action_url", "/"),
            "notification_id": notification.get("id")
        },
        "requireInteraction": notification.get("priority") == "high"
    }
