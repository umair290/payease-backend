from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User, Wallet
from models.bill_split import BillSplitGroup, BillSplitMember
import bcrypt
from datetime import datetime

split_bp = Blueprint('split', __name__)


def _add_notification(user_id, title, message, notif_type='info', icon='bell'):
    try:
        from routes.notifications import add_notification
        add_notification(user_id, title=title, message=message, notif_type=notif_type, icon=icon)
    except Exception as e:
        print(f"Notification error: {e}")


@split_bp.route('/create', methods=['POST'])
@jwt_required()
def create_split():
    user_id = int(get_jwt_identity())  # ← cast to int
    data    = request.get_json()

    title             = (data.get('title') or '').strip()[:200]
    description       = (data.get('description') or '').strip()[:500]
    total_amount      = data.get('total_amount')
    members_data      = data.get('members', [])
    split_type        = data.get('split_type', 'equal')
    creator_share_amt = data.get('creator_share_amount')

    if not title:
        return jsonify({'error': 'Title is required'}), 400
    try:
        total_amount = round(float(total_amount), 2)
        if total_amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid total amount'}), 400

    if not members_data or len(members_data) < 1:
        return jsonify({'error': 'At least 1 member is required'}), 400
    if len(members_data) > 19:
        return jsonify({'error': 'Maximum 19 additional members per split'}), 400

    creator        = User.query.get(user_id)
    creator_wallet = Wallet.query.filter_by(user_id=user_id).first()
    if not creator or not creator_wallet:
        return jsonify({'error': 'User not found'}), 404

    resolved_members = []
    wallet_numbers   = set()

    for m in members_data:
        wn = (m.get('wallet_number') or '').strip().upper()
        if not wn or wn == creator_wallet.wallet_number:
            continue
        if wn in wallet_numbers:
            continue
        wallet_numbers.add(wn)

        wallet = Wallet.query.filter_by(wallet_number=wn).first()
        if not wallet:
            return jsonify({'error': f'Wallet not found: {wn}'}), 404

        member_user  = User.query.get(wallet.user_id)
        share_amount = round(float(m.get('share_amount', 0)), 2) if split_type == 'custom' else 0
        resolved_members.append({
            'wallet_number': wn,
            'user_id':       wallet.user_id,
            'full_name':     member_user.full_name if member_user else wn,
            'avatar_url':    member_user.avatar_url if member_user else None,
            'share_amount':  share_amount,
            'is_creator':    False,
        })

    if not resolved_members:
        return jsonify({'error': 'No valid members found'}), 400

    total_participants = len(resolved_members) + 1

    if split_type == 'equal':
        per_person = round(total_amount / total_participants, 2)
        for m in resolved_members:
            m['share_amount'] = per_person
        creator_share = per_person
    else:
        try:
            creator_share = round(float(creator_share_amt), 2)
            if creator_share < 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({'error': 'Enter a valid amount for your own share'}), 400

        total_shares = sum(m['share_amount'] for m in resolved_members) + creator_share
        if abs(total_shares - total_amount) > 1:
            return jsonify({'error': f'All shares including yours ({total_shares:.0f}) must equal total ({total_amount:.0f})'}), 400

    creator_entry = {
        'wallet_number': creator_wallet.wallet_number,
        'user_id':       user_id,
        'full_name':     creator.full_name,
        'avatar_url':    creator.avatar_url,
        'share_amount':  creator_share,
        'is_creator':    True,
    }
    all_members = [creator_entry] + resolved_members

    try:
        group = BillSplitGroup(
            title        = title,
            description  = description,
            total_amount = total_amount,
            created_by   = user_id,
            status       = 'open',
        )
        db.session.add(group)
        db.session.flush()

        for m in all_members:
            member = BillSplitMember(
                group_id      = group.id,
                user_id       = m['user_id'],
                wallet_number = m['wallet_number'],
                full_name     = m['full_name'],
                avatar_url    = m['avatar_url'],
                share_amount  = m['share_amount'],
                status        = 'paid' if m['is_creator'] else 'pending',
                paid_at       = datetime.utcnow() if m['is_creator'] else None,
            )
            db.session.add(member)

        db.session.commit()

        for m in resolved_members:
            if m['user_id']:
                _add_notification(
                    m['user_id'],
                    title      = "Bill Split Request",
                    message    = f"{creator.full_name} added you to '{title}'. Your share: PKR {m['share_amount']:,.0f}",
                    notif_type = 'info',
                    icon       = 'split'
                )

        return jsonify({'message': 'Split created', 'group': group.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@split_bp.route('/list', methods=['GET'])
@jwt_required()
def list_splits():
    user_id = int(get_jwt_identity())  # ← cast to int
    wallet  = Wallet.query.filter_by(user_id=user_id).first()
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404

    created = BillSplitGroup.query.filter_by(created_by=user_id).order_by(BillSplitGroup.created_at.desc()).all()

    memberships = (
        BillSplitMember.query
        .filter_by(wallet_number=wallet.wallet_number)
        .join(BillSplitGroup, BillSplitGroup.id == BillSplitMember.group_id)
        .filter(BillSplitGroup.created_by != user_id)
        .all()
    )
    member_group_ids = {m.group_id for m in memberships}
    member_groups    = BillSplitGroup.query.filter(BillSplitGroup.id.in_(member_group_ids)).order_by(BillSplitGroup.created_at.desc()).all()
    my_shares        = {m.group_id: m for m in memberships}

    return jsonify({
        'created': [g.to_dict() for g in created],
        'member':  [{**g.to_dict(), 'my_share': my_shares[g.id].to_dict()} for g in member_groups],
    }), 200


@split_bp.route('/<int:group_id>', methods=['GET'])
@jwt_required()
def get_split(group_id):
    user_id = int(get_jwt_identity())  # ← cast to int
    group   = BillSplitGroup.query.get(group_id)
    if not group:
        return jsonify({'error': 'Split not found'}), 404

    wallet     = Wallet.query.filter_by(user_id=user_id).first()
    is_creator = group.created_by == user_id
    is_member  = wallet and any(m.wallet_number == wallet.wallet_number for m in group.members)

    if not is_creator and not is_member:
        return jsonify({'error': 'Access denied'}), 403

    return jsonify({'group': group.to_dict()}), 200


@split_bp.route('/pay', methods=['POST'])
@jwt_required()
def pay_share():
    user_id  = int(get_jwt_identity())  # ← cast to int
    data     = request.get_json()
    group_id = data.get('group_id')
    pin      = str(data.get('pin', '')).strip()

    if not group_id or not pin or len(pin) != 4:
        return jsonify({'error': 'Group ID and 4-digit PIN required'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if not bcrypt.checkpw(pin.encode('utf-8'), user.pin.encode('utf-8')):
        return jsonify({'error': 'Incorrect PIN'}), 401

    wallet = Wallet.query.filter_by(user_id=user_id).first()
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404

    group = BillSplitGroup.query.get(group_id)
    if not group:
        return jsonify({'error': 'Split not found'}), 404
    if group.status == 'settled':
        return jsonify({'error': 'This split is already settled'}), 400

    if group.created_by == user_id:  # now both ints — works correctly
        return jsonify({'error': 'As the creator your share is already marked as paid'}), 400

    my_member = next((m for m in group.members if m.wallet_number == wallet.wallet_number), None)
    if not my_member:
        return jsonify({'error': 'You are not a member of this split'}), 403
    if my_member.status == 'paid':
        return jsonify({'error': 'You have already paid your share'}), 400

    share = float(my_member.share_amount)
    if float(wallet.balance) < share:
        return jsonify({'error': 'Insufficient balance'}), 400

    try:
        first_id  = min(user_id, group.created_by)
        second_id = max(user_id, group.created_by)
        wallets   = {w.user_id: w for w in Wallet.query.filter(
            Wallet.user_id.in_([first_id, second_id])
        ).with_for_update().all()}

        payer_wallet   = wallets[user_id]
        creator_wallet = wallets[group.created_by]

        if float(payer_wallet.balance) < share:
            return jsonify({'error': 'Insufficient balance'}), 400

        payer_wallet.balance   = round(float(payer_wallet.balance)   - share, 2)
        creator_wallet.balance = round(float(creator_wallet.balance) + share, 2)

        from models import Transaction
        db.session.add(Transaction(
            user_id=user_id, from_wallet=payer_wallet.wallet_number,
            to_wallet=creator_wallet.wallet_number, amount=share,
            type='transfer', direction='debit',
            description=f"Bill split: {group.title}", status='completed',
        ))
        db.session.add(Transaction(
            user_id=group.created_by, from_wallet=payer_wallet.wallet_number,
            to_wallet=creator_wallet.wallet_number, amount=share,
            type='transfer', direction='credit',
            description=f"Bill split: {group.title}", status='completed',
        ))

        my_member.status  = 'paid'
        my_member.paid_at = datetime.utcnow()

        if all(m.status == 'paid' for m in group.members):
            group.status = 'settled'

        db.session.commit()

        _add_notification(
            group.created_by,
            title   = "Split Payment Received",
            message = f"{user.full_name} paid their share of PKR {share:,.0f} for '{group.title}'.",
            notif_type = 'success',
            icon    = 'receive'
        )

        return jsonify({
            'message':     'Payment successful',
            'new_balance': round(float(payer_wallet.balance), 2),
            'group':       group.to_dict(),
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@split_bp.route('/remind', methods=['POST'])
@jwt_required()
def remind_members():
    user_id  = int(get_jwt_identity())  # ← cast to int
    data     = request.get_json()
    group_id = data.get('group_id')

    group = BillSplitGroup.query.get(group_id)
    if not group:
        return jsonify({'error': 'Split not found'}), 404
    if group.created_by != user_id:  # now both ints — works correctly
        return jsonify({'error': 'Only the creator can send reminders'}), 403

    user    = User.query.get(user_id)
    pending = [m for m in group.members if m.status == 'pending' and m.user_id != user_id]

    for m in pending:
        if m.user_id:
            _add_notification(
                m.user_id,
                title      = "Payment Reminder",
                message    = f"{user.full_name} reminded you to pay PKR {float(m.share_amount):,.0f} for '{group.title}'.",
                notif_type = 'warning',
                icon       = 'reminder'
            )

    return jsonify({'message': f'Reminder sent to {len(pending)} member(s)'}), 200


@split_bp.route('/settle', methods=['POST'])
@jwt_required()
def settle_split():
    user_id  = int(get_jwt_identity())  # ← cast to int
    data     = request.get_json()
    group_id = data.get('group_id')

    group = BillSplitGroup.query.get(group_id)
    if not group:
        return jsonify({'error': 'Split not found'}), 404
    if group.created_by != user_id:  # now both ints — works correctly
        return jsonify({'error': 'Only the creator can settle this split'}), 403

    group.status = 'settled'
    db.session.commit()
    return jsonify({'message': 'Split settled', 'group': group.to_dict()}), 200


@split_bp.route('/<int:group_id>', methods=['DELETE'])
@jwt_required()
def delete_split(group_id):
    user_id = int(get_jwt_identity())  # ← cast to int
    group   = BillSplitGroup.query.get(group_id)
    if not group:
        return jsonify({'error': 'Split not found'}), 404
    if group.created_by != user_id:  # now both ints — works correctly
        return jsonify({'error': 'Only the creator can delete this split'}), 403

    db.session.delete(group)
    db.session.commit()
    return jsonify({'message': 'Split deleted'}), 200