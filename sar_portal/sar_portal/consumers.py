import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .db_connector import get_db
from bson import ObjectId
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'chat_{self.room_id}'
        self.user_id = await self.get_user_id_from_session()
        if not self.user_id:
            await self.close()
            return
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()
        last_read_id = await self.mark_messages_read()
        if last_read_id:
            await self.channel_layer.group_send(self.room_group, {
                'type': 'chat_read_receipt',
                'reader_id': self.user_id,
                'last_read_id': last_read_id,
            })

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception:
            return
        msg_type = data.get('type')
        if msg_type == 'message':
            content = data.get('content', '').strip()
            if not content:
                return
            msg = await self.save_message(content)
            await self.channel_layer.group_send(self.room_group, {
                'type': 'chat_message',
                'message': msg,
            })
        elif msg_type == 'reaction':
            msg_id = data.get('msg_id', '')
            emoji = data.get('emoji', '')
            if not msg_id or not emoji:
                return
            result = await self.toggle_reaction(msg_id, emoji)
            await self.channel_layer.group_send(self.room_group, {
                'type': 'chat_reaction',
                'msg_id': msg_id,
                'reactions': result,
                'reactor_id': self.user_id,
            })

    async def chat_message(self, event):
        msg = event['message']
        if msg and msg.get('sender_id') != self.user_id:
            read_id = await self.mark_single_message_read(msg['id'])
            if read_id:
                await self.channel_layer.group_send(self.room_group, {
                    'type': 'chat_read_receipt',
                    'reader_id': self.user_id,
                    'last_read_id': read_id,
                })
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': msg,
        }))

    async def chat_reaction(self, event):
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'msg_id': event['msg_id'],
            'reactions': event['reactions'],
        }))

    async def chat_read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'reader_id': event['reader_id'],
            'last_read_id': event['last_read_id'],
        }))

    @database_sync_to_async
    def get_user_id_from_session(self):
        session = self.scope.get('session')
        if session is None:
            return None
        return session.get('user_id')

    @database_sync_to_async
    def mark_messages_read(self):
        db = get_db()
        parts = self.room_id.split('_')
        other_ids = [p for p in parts if p != self.user_id]
        latest = list(db.sar_chat_messages.find(
            {'room_id': self.room_id, 'sender_id': {'$in': other_ids}, 'read': {'$ne': True}},
            {'_id': 1}
        ).sort('sent_at', -1).limit(1))
        if not latest:
            return None
        db.sar_chat_messages.update_many(
            {'room_id': self.room_id, 'sender_id': {'$in': other_ids}, 'read': {'$ne': True}},
            {'$set': {'read': True}}
        )
        return str(latest[0]['_id'])

    @database_sync_to_async
    def mark_single_message_read(self, msg_id):
        db = get_db()
        try:
            result = db.sar_chat_messages.update_one(
                {'_id': ObjectId(msg_id), 'read': {'$ne': True}},
                {'$set': {'read': True}}
            )
            if result.modified_count == 0:
                return None
        except Exception:
            return None
        return msg_id

    @database_sync_to_async
    def save_message(self, content):
        db = get_db()
        user = db.sar_users.find_one({'_id': ObjectId(self.user_id)}, {'name': 1, 'profile_pic': 1})
        if not user:
            return None
        now_utc = datetime.utcnow()
        now_ist = datetime.now(IST)
        msg_doc = {
            'room_id': self.room_id,
            'sender_id': self.user_id,
            'sender_name': user.get('name', ''),
            'content': content,
            'sent_at': now_utc,
            'reactions': {},
            'read': False,
        }
        result = db.sar_chat_messages.insert_one(msg_doc)
        parts = self.room_id.split('_')
        other_parts = [p for p in parts if p != self.user_id]
        unread_inc = {}
        for p in other_parts:
            unread_inc[f'unread.{p}'] = 1
        set_doc = {
            'last_message': content[:120],
            'last_message_at': now_utc,
            'last_sender_id': self.user_id,
        }
        update_doc = {'$set': set_doc}
        if unread_inc:
            update_doc['$inc'] = unread_inc
        db.sar_chat_rooms.update_one({'room_id': self.room_id}, update_doc, upsert=True)
        for recipient_id in other_parts:
            existing = db.sar_notifications.find_one({
                'user_id': recipient_id,
                'type': 'dm',
                'reference_id': self.room_id,
                'read': False,
            })
            if not existing:
                db.sar_notifications.insert_one({
                    'user_id': recipient_id,
                    'type': 'dm',
                    'title': 'New Message',
                    'message': f"{user.get('name', '')} sent you a message: {content[:80]}",
                    'link': f'/chat/{self.user_id}/',
                    'reference_id': self.room_id,
                    'read': False,
                    'created_at': now_utc,
                })
        return {
            'id': str(result.inserted_id),
            'sender_id': self.user_id,
            'sender_name': user.get('name', ''),
            'content': content,
            'sent_at': now_ist.strftime('%b %d, %Y %I:%M %p'),
            'reactions': {},
            'read': False,
        }

    @database_sync_to_async
    def toggle_reaction(self, msg_id, emoji):
        db = get_db()
        try:
            msg = db.sar_chat_messages.find_one({'_id': ObjectId(msg_id)})
        except Exception:
            return {}
        if not msg:
            return {}
        reactions = msg.get('reactions', {})
        if emoji not in reactions:
            reactions[emoji] = []
        if self.user_id in reactions[emoji]:
            reactions[emoji].remove(self.user_id)
        else:
            reactions[emoji].append(self.user_id)
        if not reactions[emoji]:
            del reactions[emoji]
        db.sar_chat_messages.update_one(
            {'_id': ObjectId(msg_id)},
            {'$set': {'reactions': reactions}}
        )
        return {k: len(v) for k, v in reactions.items()}

class SupportConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group = f'support_{self.user_id}'
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def support_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

class BroadcastConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group = 'broadcasts'
        self.user_id = await self.get_user_id_from_session()
        if not self.user_id:
            await self.close()
            return
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception:
            return
        if data.get('type') == 'reaction':
            msg_id = data.get('msg_id')
            emoji = data.get('emoji')
            if not msg_id or not emoji:
                return
            user_name = await self.get_user_name()
            result = await self.toggle_broadcast_reaction(msg_id, emoji, user_name)
            await self.channel_layer.group_send(self.room_group, {
                'type': 'broadcast_reaction',
                'msg_id': msg_id,
                'reactions': result,
            })

    async def broadcast_reaction(self, event):
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'msg_id': event['msg_id'],
            'reactions': event['reactions'],
        }))

    @database_sync_to_async
    def get_user_id_from_session(self):
        session = self.scope.get('session')
        return session.get('user_id') if session else None

    @database_sync_to_async
    def get_user_name(self):
        db = get_db()
        user = db.sar_users.find_one({'_id': ObjectId(self.user_id)})
        return user.get('name', '') if user else ''

    @database_sync_to_async
    def toggle_broadcast_reaction(self, msg_id, emoji, user_name):
        db = get_db()
        bc = db.sar_broadcasts.find_one({'_id': ObjectId(msg_id)})
        if not bc:
            return {}
        reactions = bc.get('reactions', {})
        if reactions.get(self.user_id, {}).get('emoji') == emoji:
            del reactions[self.user_id]
        else:
            reactions[self.user_id] = {'emoji': emoji, 'name': user_name}
        db.sar_broadcasts.update_one({'_id': ObjectId(msg_id)}, {'$set': {'reactions': reactions}})
        counts = {}
        for uid, r in reactions.items():
            counts[r['emoji']] = counts.get(r['emoji'], 0) + 1
        return counts