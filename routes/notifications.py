from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models.notification import Notification
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__)


def add_notification(user_id, title, message, notif_type='info', icon='bell'):
    """
    Call this from any route to create a notification.
    Keeps last 50 per user — deletes oldest if over limit.
    """
    try:
        notif = Notification(
            user_id = int(user_id),
            title   = str(title)[:200],
            message = str(message),
            type    = notif_type,
            icon    = icon,
            read    = False,
        )
        db.session.add(notif)
        db.session.flush()

        # ── Keep only latest 50 per user ──
        total = Notification.query.filter_by(user_id=int(user_id)).count()
        if total > 50:
            oldest = (
                Notification.query
                .filter_by(user_id=int(user_id))
                .order_by(Notification.created_at.asc())
                .limit(total - 50)
                .all()
            )
            for old in oldest:
                db.session.delete(old)

        db.session.commit()
        return notif
    except Exception as e:
        db.session.rollback()
        print(f"Notification error: {e}")
        return None


@notifications_bp.route('/', methods=['GET'])
@jwt_required()
def get_notifications():
    user_id = int(get_jwt_identity())
    notifs  = (
        Notification.query
        .filter_by(user_id=user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    unread = sum(1 for n in notifs if not n.read)
    return jsonify({
        'notifications': [n.to_dict() for n in notifs],
        'unread_count':  unread,
    }), 200


@notifications_bp.route('/mark-all-read', methods=['POST'])
@jwt_required()
def mark_all_read():
    user_id = int(get_jwt_identity())
    Notification.query.filter_by(user_id=user_id, read=False).update({'read': True})
    db.session.commit()
    return jsonify({'message': 'All marked as read'}), 200


@notifications_bp.route('/<int:notif_id>/read', methods=['POST'])
@jwt_required()
def mark_read(notif_id):
    user_id = int(get_jwt_identity())
    notif   = Notification.query.filter_by(id=notif_id, user_id=user_id).first()
    if notif:
        notif.read = True
        db.session.commit()
    return jsonify({'message': 'Marked as read'}), 200


@notifications_bp.route('/clear', methods=['DELETE'])
@jwt_required()
def clear_notifications():
    user_id = int(get_jwt_identity())
    Notification.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify({'message': 'Notifications cleared'}), 200