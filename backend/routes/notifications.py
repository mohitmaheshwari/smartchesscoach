"""
Notifications Routes
====================

Handles notification management, push notifications, and device registration.

Endpoints:
- GET /notifications - Get user's notifications
- POST /notifications/read - Mark notification(s) as read
- POST /notifications/{notification_id}/read - Mark single notification read
- POST /notifications/read-all - Mark all notifications read
- POST /notifications/{notification_id}/dismiss - Dismiss a notification
- GET /notifications/push-payload/{notification_id} - Get push payload
- POST /notifications/register-device - Register for push notifications
- DELETE /notifications/unregister-device - Unregister from push notifications
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Create router for notifications endpoints
router = APIRouter(prefix="/notifications", tags=["Notifications"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for notifications routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user

# Import notification services
from notification_service import (
    get_user_notifications,
    get_unread_count,
    mark_notification_read,
    dismiss_notification,
    get_push_notification_payload
)


# ==================== MODELS ====================

class RegisterDeviceRequest(BaseModel):
    push_token: str
    platform: str  # 'ios' or 'android'


# ==================== ENDPOINTS ====================

@router.get("")
async def get_notifications(
    unread_only: bool = False,
    limit: int = 20,
    user: User = Depends(get_current_user)
):
    """
    Get user's notifications.
    """
    global db
    notifications = await get_user_notifications(db, user.user_id, unread_only, limit)
    unread_count = await get_unread_count(db, user.user_id)
    
    return {
        "notifications": notifications,
        "unread_count": unread_count
    }


@router.post("/read")
async def mark_notifications_read(
    notification_id: str = None,
    user: User = Depends(get_current_user)
):
    """
    Mark notification(s) as read.
    If notification_id is provided, marks only that notification.
    Otherwise marks all as read.
    """
    global db
    success = await mark_notification_read(db, user.user_id, notification_id)
    return {"success": success}


@router.post("/{notification_id}/read")
async def mark_single_notification_read(notification_id: str, user: User = Depends(get_current_user)):
    """Mark a single notification as read"""
    global db
    result = await db.notifications.update_one(
        {"user_id": user.user_id, "notification_id": notification_id},
        {"$set": {"read": True}}
    )
    return {"success": result.modified_count > 0}


@router.post("/read-all")
async def mark_all_notifications_read(user: User = Depends(get_current_user)):
    """Mark all notifications as read"""
    global db
    result = await db.notifications.update_many(
        {"user_id": user.user_id, "read": False},
        {"$set": {"read": True}}
    )
    return {"success": True, "updated": result.modified_count}


@router.post("/{notification_id}/dismiss")
async def dismiss_user_notification(
    notification_id: str,
    user: User = Depends(get_current_user)
):
    """
    Dismiss a notification.
    """
    global db
    success = await dismiss_notification(db, user.user_id, notification_id)
    return {"success": success}


@router.get("/push-payload/{notification_id}")
async def get_notification_push_payload(
    notification_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get push notification payload for browser Notification API.
    """
    global db
    from bson import ObjectId
    notification = await db.notifications.find_one(
        {"_id": ObjectId(notification_id), "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification["id"] = notification_id
    return get_push_notification_payload(notification)


@router.post("/register-device")
async def register_push_device(request: RegisterDeviceRequest, user: User = Depends(get_current_user)):
    """Register a device for push notifications"""
    global db
    await db.users.update_one(
        {"user_id": user.user_id},
        {
            "$set": {
                "push_token": request.push_token,
                "push_platform": request.platform,
                "push_registered_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    return {"message": "Device registered for push notifications"}


@router.delete("/unregister-device")
async def unregister_push_device(user: User = Depends(get_current_user)):
    """Unregister device from push notifications"""
    global db
    await db.users.update_one(
        {"user_id": user.user_id},
        {
            "$unset": {
                "push_token": "",
                "push_platform": "",
                "push_registered_at": ""
            }
        }
    )
    return {"message": "Device unregistered from push notifications"}
