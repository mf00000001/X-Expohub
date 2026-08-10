"""
WebSocket — 游戏实时通信
─────────────────────────
支持：
  - 房间创建 / 加入 / 离开
  - 实时位置同步广播
  - 技能释放广播
  - 聊天消息

消息格式均为 JSON
"""

import json
import time
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter()


# ──────────────────── 房间管理 ────────────────────

class Room:
    """游戏房间"""
    def __init__(self, room_id: str, name: str = ""):
        self.room_id = room_id
        self.name = name
        self.clients: Dict[str, WebSocket] = {}   # player_id → WebSocket
        self.created_at = time.time()

    def add_client(self, player_id: str, ws: WebSocket):
        self.clients[player_id] = ws

    def remove_client(self, player_id: str):
        self.clients.pop(player_id, None)

    @property
    def player_count(self) -> int:
        return len(self.clients)

    @property
    def player_ids(self) -> Set[str]:
        return set(self.clients.keys())


class RoomManager:
    """全局房间管理器"""
    def __init__(self):
        self._rooms: Dict[str, Room] = {}

    def create_room(self, room_id: str, name: str = "") -> Room:
        if room_id in self._rooms:
            raise ValueError(f"房间 {room_id} 已存在")
        room = Room(room_id, name)
        self._rooms[room_id] = room
        return room

    def get_room(self, room_id: str) -> Room:
        if room_id not in self._rooms:
            raise ValueError(f"房间 {room_id} 不存在")
        return self._rooms[room_id]

    def remove_room(self, room_id: str):
        self._rooms.pop(room_id, None)

    def list_rooms(self) -> list[dict]:
        return [
            {
                "room_id": r.room_id,
                "name": r.name,
                "player_count": r.player_count,
            }
            for r in self._rooms.values()
        ]


room_manager = RoomManager()


# ──────────────────── 消息格式（文档用途） ────────────────────

"""
所有 WebSocket 消息均为 JSON 对象，通过 "type" 字段区分：

1. 加入房间 (客户端 → 服务端)
   {"type": "join", "room_id": "abc123", "player_id": "player_1"}

2. 离开房间 (客户端 → 服务端)
   {"type": "leave"}

3. 位置同步 (客户端 → 服务端 → 房间内广播)
   {"type": "position", "player_id": "player_1", "x": 1234.5, "y": 6789.0, "rotation": 45.0}

4. 技能释放 (客户端 → 服务端 → 房间内广播)
   {"type": "skill_cast", "player_id": "player_1", "skill_slot": "Q",
    "target_x": 1500.0, "target_y": 2200.0, "timestamp": 1700000000.123}

5. 聊天消息 (客户端 → 服务端 → 房间内广播)
   {"type": "chat", "player_id": "player_1", "message": "Hello!"}

6. 系统消息 (服务端 → 客户端)
   {"type": "system", "message": "player_2 加入了房间"}

7. 房间状态 (服务端 → 客户端)
   {"type": "room_state", "room_id": "abc123", "players": ["player_1", "player_2"]}

8. 错误消息 (服务端 → 客户端)
   {"type": "error", "message": "房间不存在"}
"""


# ──────────────────── WebSocket 端点 ────────────────────

@ws_router.websocket("/ws/game")
async def game_websocket(ws: WebSocket):
    """
    游戏 WebSocket 主端点。
    客户端连接后发送 JSON 消息进行房间操作和实时通信。
    """
    await ws.accept()
    current_room: Room | None = None
    current_player_id: str | None = None

    # 发送欢迎消息
    await ws.send_json({
        "type": "system",
        "message": "已连接到 MOBA 游戏服务器",
    })

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "无效的 JSON 格式"})
                continue

            msg_type = data.get("type", "")

            # ── 加入房间 ──
            if msg_type == "join":
                room_id = data.get("room_id", "")
                player_id = data.get("player_id", "")
                if not room_id or not player_id:
                    await ws.send_json({"type": "error", "message": "缺少 room_id 或 player_id"})
                    continue

                # 如果已在其他房间，先离开
                if current_room:
                    current_room.remove_client(current_player_id)
                    await _broadcast(current_room, {
                        "type": "system",
                        "message": f"{current_player_id} 离开了房间",
                    }, exclude=current_player_id)

                # 进入新房间
                try:
                    room = room_manager.get_room(room_id)
                except ValueError:
                    room = room_manager.create_room(room_id)

                room.add_client(player_id, ws)
                current_room = room
                current_player_id = player_id

                # 通知所有人
                await _broadcast(room, {
                    "type": "system",
                    "message": f"{player_id} 加入了房间",
                })
                await _broadcast(room, {
                    "type": "room_state",
                    "room_id": room.room_id,
                    "players": list(room.player_ids),
                })

            # ── 离开房间 ──
            elif msg_type == "leave":
                if current_room and current_player_id:
                    current_room.remove_client(current_player_id)
                    await _broadcast(current_room, {
                        "type": "system",
                        "message": f"{current_player_id} 离开了房间",
                    }, exclude=current_player_id)
                    await _broadcast(current_room, {
                        "type": "room_state",
                        "room_id": current_room.room_id,
                        "players": list(current_room.player_ids),
                    })
                    # 空房间清理
                    if current_room.player_count == 0:
                        room_manager.remove_room(current_room.room_id)
                current_room = None
                current_player_id = None

            # ── 位置同步 ──
            elif msg_type == "position":
                if not current_room:
                    await ws.send_json({"type": "error", "message": "请先加入房间"})
                    continue
                await _broadcast(current_room, data, exclude=current_player_id)

            # ── 技能释放 ──
            elif msg_type == "skill_cast":
                if not current_room:
                    await ws.send_json({"type": "error", "message": "请先加入房间"})
                    continue
                # 附加服务端时间戳
                data["server_timestamp"] = time.time()
                await _broadcast(current_room, data, exclude=current_player_id)

            # ── 聊天 ──
            elif msg_type == "chat":
                if not current_room:
                    await ws.send_json({"type": "error", "message": "请先加入房间"})
                    continue
                await _broadcast(current_room, data)

            # ── 列出房间 ──
            elif msg_type == "list_rooms":
                await ws.send_json({
                    "type": "room_list",
                    "rooms": room_manager.list_rooms(),
                })

            # ── 未知消息类型 ──
            else:
                await ws.send_json({
                    "type": "error",
                    "message": f"未知消息类型: {msg_type}",
                })

    except WebSocketDisconnect:
        # 断开时自动离开房间
        if current_room and current_player_id:
            current_room.remove_client(current_player_id)
            await _broadcast(current_room, {
                "type": "system",
                "message": f"{current_player_id} 断开了连接",
            }, exclude=current_player_id)
            await _broadcast(current_room, {
                "type": "room_state",
                "room_id": current_room.room_id,
                "players": list(current_room.player_ids),
            })
            if current_room.player_count == 0:
                room_manager.remove_room(current_room.room_id)


async def _broadcast(room: Room, data: dict, exclude: str | None = None):
    """向房间内所有客户端广播消息，可排除指定 player_id"""
    for pid, client_ws in list(room.clients.items()):
        if pid == exclude:
            continue
        try:
            await client_ws.send_json(data)
        except Exception:
            # 客户端可能已断开但尚未清理，忽略发送失败
            pass
