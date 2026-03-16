from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models.user import User
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__)

# In-memory notifications store (will move to DB later)
notifications_store = {}

def add_notification(user_id, title, message, notif_type='info', icon='bell'):
    user_id = str(user_id)
    if user_id not in notifications_store:
        notifications_store[user_id] = []
    
    notification = {
        'id': len(notifications_store[user_id]) + 1,
        'title': title,
        'message': message,
        'type': notif_type,  # info, success, warning, error
        'icon': icon,
        'read': False,
        'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }
    notifications_store[user_id].insert(0, notification)
    
    # Keep only last 50 notifications
    notifications_store[user_id] = notifications_store[user_id][:50]
    return notification


@notifications_bp.route('/', methods=['GET'])
@jwt_required()
def get_notifications():
    user_id = str(get_jwt_identity())
    notifs = notifications_store.get(user_id, [])
    unread = len([n for n in notifs if not n['read']])
    return jsonify({
        'notifications': notifs,
        'unread_count': unread
    }), 200


@notifications_bp.route('/read/<int:notif_id>', methods=['POST'])
@jwt_required()
def mark_read(notif_id):
    user_id = str(get_jwt_identity())
    notifs = notifications_store.get(user_id, [])
    for n in notifs:
        if n['id'] == notif_id:
            n['read'] = True
            break
    return jsonify({'message': 'Marked as read'}), 200


@notifications_bp.route('/read-all', methods=['POST'])
@jwt_required()
def mark_all_read():
    user_id = str(get_jwt_identity())
    notifs = notifications_store.get(user_id, [])
    for n in notifs:
        n['read'] = True
    return jsonify({'message': 'All marked as read'}), 200


@notifications_bp.route('/clear', methods=['DELETE'])
@jwt_required()
def clear_notifications():
    user_id = str(get_jwt_identity())
    notifications_store[user_id] = []
    return jsonify({'message': 'Notifications cleared'}), 200