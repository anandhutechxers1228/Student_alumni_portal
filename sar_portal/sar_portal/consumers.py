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
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def chat_reaction(self, event):
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'msg_id': event['msg_id'],
            'reactions': event['reactions'],
        }))

    @database_sync_to_async
    def get_user_id_from_session(self):
        session = self.scope.get('session')
        if session is None:
            return None
        return session.get('user_id')

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
            'sender_pic': user.get('profile_pic', ''),
            'content': content,
            'sent_at': now_utc,
            'reactions': {},
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
        return {
            'id': str(result.inserted_id),
            'sender_id': self.user_id,
            'sender_name': user.get('name', ''),
            'sender_pic': user.get('profile_pic', ''),
            'content': content,
            'sent_at': now_ist.strftime('%b %d, %Y %I:%M %p'),
            'reactions': {},
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
