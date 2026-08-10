"""消息 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.dependencies import require_any_user
from app.database.session import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.message import MessageCreate, MessageResponse
from app.services import message_service

router = APIRouter(prefix="/messages", tags=["消息"])


@router.post("/", response_model=ApiResponse[MessageResponse], status_code=201)
async def send_message(
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_user),
):
    """发送消息"""
    message = message_service.send_message(db, current_user.id, data)
    return ApiResponse(data=MessageResponse.model_validate(message))


@router.get("/", response_model=ApiResponse[PaginatedResponse[MessageResponse]])
async def list_messages(
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_user),
):
    """获取我的消息列表"""
    messages, total = message_service.get_user_messages(
        db, current_user.id, page, page_size, unread_only
    )
    total_pages = (total + page_size - 1) // page_size
    return ApiResponse(data=PaginatedResponse(
        items=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ))


@router.get("/conversation/{user_id}", response_model=ApiResponse[PaginatedResponse[MessageResponse]])
async def get_conversation(
    user_id: int,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_user),
):
    """获取与指定用户的会话"""
    messages, total = message_service.get_conversation(
        db, current_user.id, user_id, page, page_size
    )
    total_pages = (total + page_size - 1) // page_size
    return ApiResponse(data=PaginatedResponse(
        items=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ))


@router.put("/{message_id}/read", response_model=ApiResponse[MessageResponse])
async def mark_as_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_user),
):
    """标记消息为已读"""
    message = message_service.mark_as_read(db, message_id, current_user.id)
    return ApiResponse(data=MessageResponse.model_validate(message))


@router.get("/unread/count", response_model=ApiResponse[dict])
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user=Depends(require_any_user),
):
    """获取未读消息数"""
    count = message_service.get_unread_count(db, current_user.id)
    return ApiResponse(data={"unread_count": count})


# WebSocket 连接管理器
class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        self.active_connections.pop(user_id, None)

    async def send_message(self, user_id: int, message: dict):
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_json(message)


manager = ConnectionManager()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, user_id: int):
    """WebSocket 实时聊天"""
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            # 处理消息...
            receiver_id = data.get("receiver_id")
            content = data.get("content")
            if receiver_id and content:
                await manager.send_message(receiver_id, {
                    "sender_id": user_id,
                    "content": content,
                    "type": "chat",
                })
    except WebSocketDisconnect:
        manager.disconnect(user_id)
