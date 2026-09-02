"""
消息路由（Messages）

端点（匹配前端 expo-hub-frontend/src/api/message.ts）：
- GET    /messages/conversations                        当前用户会话列表
- GET    /messages/user/{user_id}                       与指定用户的聊天记录（分页）
- POST   /messages                                      发送消息（body: receiver_id, title, content）
- POST   /messages/{message_id}/read                    标记单条消息已读
- GET    /messages/unread-count                         总未读消息数

保留的旧 conversation 路由（别名）：
- GET    /messages/conversations/{conversation_id}       会话详情
- GET    /messages/conversations/{conversation_id}/messages  会话消息列表
- POST   /messages/conversations/{conversation_id}/messages  发送消息（旧）
- POST   /messages/conversations                         发起新会话
- PUT    /messages/conversations/{conversation_id}/read     标记已读（旧）
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, and_

from app.models.base import get_db
from app.models.user import User
from app.models.message import Message, Conversation
from app.core.deps import get_current_active_user
from app.core.exceptions import NotFound, Forbidden, BadRequest

router = APIRouter(prefix="/messages", tags=["消息"])


# ============================================================
# Pydantic Schemas
# ============================================================

class SendMessageRequest(BaseModel):
    """发送消息请求（前端 POST /messages）"""
    receiver_id: int
    title: Optional[str] = None
    content: str


class StartConversationRequest(BaseModel):
    """发起新会话请求"""
    receiver_id: int
    content: str


class ConvSendRequest(BaseModel):
    """旧接口：会话内发送消息请求"""
    content: str


# ============================================================
# 辅助函数
# ============================================================

def _message_to_dict(message: Message) -> dict:
    """将 Message 模型转为前端响应格式"""
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "sender_name": message.sender_name,
        "receiver_id": message.receiver_id,
        "title": message.title,
        "content": message.content,
        "is_read": message.is_read,
        "read_at": message.read_at,
        "created_at": message.created_at,
    }


def _get_other_user_id(conversation: Conversation, current_user_id: int) -> int:
    """返回会话中另一方的 user_id"""
    if conversation.user1_id == current_user_id:
        return conversation.user2_id
    return conversation.user1_id


def _conversation_to_dict(db: Session, conversation: Conversation, current_user_id: int) -> dict:
    """将 Conversation 模型转为前端响应格式"""
    user1 = db.query(User).filter(User.id == conversation.user1_id).first()
    user2 = db.query(User).filter(User.id == conversation.user2_id).first()

    participants = []
    for u in (user1, user2):
        if u:
            participants.append({
                "id": u.id,
                "username": u.username,
                "avatar_url": u.avatar_url,
            })

    last_message = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .first()
    )

    unread_count = (
        db.query(func.count(Message.id))
        .filter(
            Message.conversation_id == conversation.id,
            Message.receiver_id == current_user_id,
            Message.is_read == False,
        )
        .scalar()
    ) or 0

    return {
        "id": conversation.id,
        "participants": participants,
        "last_message": _message_to_dict(last_message) if last_message else None,
        "unread_count": unread_count,
        "updated_at": conversation.updated_at,
    }


def _paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
    """构建分页响应"""
    return {
        "list": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }


def _find_or_create_conversation(db: Session, user1_id: int, user2_id: int) -> Conversation:
    """查找两个用户间的会话，不存在则创建"""
    conversation = (
        db.query(Conversation)
        .filter(
            or_(
                and_(Conversation.user1_id == user1_id, Conversation.user2_id == user2_id),
                and_(Conversation.user1_id == user2_id, Conversation.user2_id == user1_id),
            )
        )
        .first()
    )
    if not conversation:
        now = datetime.now(timezone.utc).isoformat()
        conversation = Conversation(
            user1_id=user1_id,
            user2_id=user2_id,
            unread_count=0,
            updated_at=now,
        )
        db.add(conversation)
        db.flush()
    return conversation


# ============================================================
# 新端点（匹配前端 message.ts）
# ============================================================

@router.get("/conversations")
def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的会话列表

    按 updated_at 降序排列，支持分页。
    """
    q = db.query(Conversation).filter(
        or_(
            Conversation.user1_id == current_user.id,
            Conversation.user2_id == current_user.id,
        )
    )

    total = q.count()
    conversations = (
        q.order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [_conversation_to_dict(db, c, current_user.id) for c in conversations]

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(items, total, page, page_size),
    }


@router.get("/user/{user_id}")
def get_messages_with_user(
    user_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取与指定用户的聊天记录

    前端调用：GET /messages/user/{userId}?page=1
    自动查找（或创建）双方会话，按时间升序返回消息列表。
    """
    # 验证目标用户存在
    other = db.query(User).filter(User.id == user_id).first()
    if not other:
        raise NotFound(message="用户不存在")

    # 不能和自己对话
    if user_id == current_user.id:
        raise BadRequest(message="不能和自己对话")

    # 查找或创建会话
    conversation = _find_or_create_conversation(db, current_user.id, user_id)

    q = db.query(Message).filter(Message.conversation_id == conversation.id)
    total = q.count()
    messages = (
        q.order_by(Message.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_message_to_dict(m) for m in messages], total, page, page_size
        ),
    }


@router.post("")
def send_message(
    data: SendMessageRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """发送消息

    前端调用：POST /messages
    请求体：{ receiver_id, title?, content }
    自动查找或创建会话，将消息追加到会话中。
    """
    # 验证接收者存在
    receiver = db.query(User).filter(User.id == data.receiver_id).first()
    if not receiver:
        raise NotFound(message="接收者不存在")

    # 不能给自己发
    if data.receiver_id == current_user.id:
        raise BadRequest(message="不能给自己发消息")

    # 查找或创建会话
    conversation = _find_or_create_conversation(db, current_user.id, data.receiver_id)

    now = datetime.now(timezone.utc).isoformat()

    message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        sender_name=current_user.nickname or current_user.username,
        receiver_id=data.receiver_id,
        title=data.title,
        content=data.content,
        is_read=False,
        created_at=now,
    )
    db.add(message)

    # 更新会话时间
    conversation.updated_at = now

    db.commit()
    db.refresh(message)

    return {
        "success": True,
        "code": "OK",
        "message": "发送成功",
        "data": _message_to_dict(message),
    }


@router.post("/{message_id}/read")
def mark_message_read(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """标记单条消息为已读

    前端调用：POST /messages/{messageId}/read
    """
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise NotFound(message="消息不存在")

    # 只能标记发给自己的消息
    if message.receiver_id != current_user.id:
        raise Forbidden(message="无权标记此消息")

    now = datetime.now(timezone.utc).isoformat()
    message.is_read = True
    message.read_at = now
    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": "已标记为已读",
        "data": _message_to_dict(message),
    }


@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的总未读消息数"""
    count = (
        db.query(func.count(Message.id))
        .filter(
            Message.receiver_id == current_user.id,
            Message.is_read == False,
        )
        .scalar()
    ) or 0

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": {"unread_count": count},
    }


# ============================================================
# 保留的旧 conversation 端点（别名/兼容）
# ============================================================

@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取单个会话详情（旧接口）"""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise NotFound(message="会话不存在")

    if current_user.id not in (conversation.user1_id, conversation.user2_id):
        raise Forbidden(message="无权查看此会话")

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _conversation_to_dict(db, conversation, current_user.id),
    }


@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取会话的消息列表（旧接口）"""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise NotFound(message="会话不存在")

    if current_user.id not in (conversation.user1_id, conversation.user2_id):
        raise Forbidden(message="无权查看此会话的消息")

    q = db.query(Message).filter(Message.conversation_id == conversation_id)
    total = q.count()
    messages = (
        q.order_by(Message.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_message_to_dict(m) for m in messages], total, page, page_size
        ),
    }


@router.post("/conversations/{conversation_id}/messages")
def send_message_in_conv(
    conversation_id: int,
    data: ConvSendRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """在已有会话中发送消息（旧接口）"""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise NotFound(message="会话不存在")

    if current_user.id not in (conversation.user1_id, conversation.user2_id):
        raise Forbidden(message="无权在此会话中发送消息")

    receiver_id = _get_other_user_id(conversation, current_user.id)

    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        raise NotFound(message="接收者不存在")

    now = datetime.now(timezone.utc).isoformat()

    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        sender_name=current_user.nickname or current_user.username,
        receiver_id=receiver_id,
        content=data.content,
        is_read=False,
        created_at=now,
    )
    db.add(message)

    conversation.updated_at = now
    db.commit()
    db.refresh(message)

    return {
        "success": True,
        "code": "OK",
        "message": "发送成功",
        "data": _message_to_dict(message),
    }


@router.post("/conversations")
def start_conversation(
    data: StartConversationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """发起新会话（旧接口）"""
    if data.receiver_id == current_user.id:
        raise BadRequest(message="不能和自己创建会话")

    receiver = db.query(User).filter(User.id == data.receiver_id).first()
    if not receiver:
        raise NotFound(message="接收者不存在")

    conversation = _find_or_create_conversation(db, current_user.id, data.receiver_id)

    now = datetime.now(timezone.utc).isoformat()

    message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        sender_name=current_user.nickname or current_user.username,
        receiver_id=data.receiver_id,
        content=data.content,
        is_read=False,
        created_at=now,
    )
    db.add(message)

    conversation.updated_at = now
    db.commit()
    db.refresh(message)

    return {
        "success": True,
        "code": "OK",
        "message": "会话创建成功",
        "data": {
            "conversation": _conversation_to_dict(db, conversation, current_user.id),
            "message": _message_to_dict(message),
        },
    }


@router.put("/conversations/{conversation_id}/read")
def mark_conv_as_read(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """标记会话已读（旧接口）"""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise NotFound(message="会话不存在")

    if current_user.id not in (conversation.user1_id, conversation.user2_id):
        raise Forbidden(message="无权操作此会话")

    unread_messages = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id,
            Message.receiver_id == current_user.id,
            Message.is_read == False,
        )
        .all()
    )

    now = datetime.now(timezone.utc).isoformat()
    count = len(unread_messages)
    for msg in unread_messages:
        msg.is_read = True
        msg.read_at = now

    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": f"已标记 {count} 条消息为已读",
        "data": {"marked_count": count},
    }



# ============================================================
# 打字状态（轻量级跨用户通知，不使用 WebSocket）
# ============================================================

# 内存存储：{ conversation_id: { user_id: last_typing_iso } }
_typing_store: dict = {}

@router.get("/typing/{conversation_id}")
def get_typing_status(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取会话中另一方的打字状态"""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise NotFound(message="会话不存在")
    if current_user.id not in (conversation.user1_id, conversation.user2_id):
        raise Forbidden(message="无权访问此会话")

    other_id = conversation.user2_id if conversation.user1_id == current_user.id else conversation.user1_id
    conv_typing = _typing_store.get(conversation_id, {})
    last_typing_at = conv_typing.get(other_id)

    from datetime import datetime as dt, timezone as tz, timedelta
    is_typing = False
    if last_typing_at:
        try:
            last_dt = dt.fromisoformat(last_typing_at)
            is_typing = (dt.now(tz.utc) - last_dt).total_seconds() < 3
        except Exception:
            pass

    return {
        "success": True,
        "code": "OK",
        "data": {"is_typing": is_typing, "user_id": other_id},
    }


@router.post("/typing/{conversation_id}")
def set_typing_status(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """设置当前用户正在输入"""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise NotFound(message="会话不存在")
    if current_user.id not in (conversation.user1_id, conversation.user2_id):
        raise Forbidden(message="无权操作此会话")

    from datetime import datetime as dt, timezone as tz
    now = dt.now(tz.utc).isoformat()
    if conversation_id not in _typing_store:
        _typing_store[conversation_id] = {}
    _typing_store[conversation_id][current_user.id] = now

    return {
        "success": True,
        "code": "OK",
        "data": {"typing": True},
    }


# ============================================================
# AI 翻译端点
# ============================================================

@router.post("/translate")
def translate_message(data: dict, db: Session = Depends(get_db)):
    """简单词典翻译（展会常用语）— 生产环境可替换为 LLM / 翻译 API"""
    text = data.get("text", "")
    target_lang = data.get("target_lang", "en")
    # 中 → 英/日/韩 常用展会短语
    translations = {
        "你好": {"en": "Hello", "ja": "こんにちは", "ko": "안녕하세요"},
        "谢谢": {"en": "Thank you", "ja": "ありがとう", "ko": "감사합니다"},
        "价格": {"en": "Price", "ja": "価格", "ko": "가격"},
        "产品": {"en": "Product", "ja": "製品", "ko": "제품"},
        "展会": {"en": "Exhibition", "ja": "展示会", "ko": "전시회"},
        "多少钱": {"en": "How much", "ja": "いくらですか", "ko": "얼마입니까"},
        "质量": {"en": "Quality", "ja": "品質", "ko": "품질"},
        "合作": {"en": "Cooperation", "ja": "協力", "ko": "협력"},
        "欢迎": {"en": "Welcome", "ja": "ようこそ", "ko": "환영합니다"},
        "再见": {"en": "Goodbye", "ja": "さようなら", "ko": "안녕히 가세요"},
        "样品": {"en": "Sample", "ja": "サンプル", "ko": "샘플"},
        "订单": {"en": "Order", "ja": "注文", "ko": "주문"},
        "发货": {"en": "Ship", "ja": "出荷", "ko": "배송"},
        "付款": {"en": "Payment", "ja": "支払い", "ko": "지불"},
        "联系方式": {"en": "Contact", "ja": "連絡先", "ko": "연락처"},
    }
    translated = translations.get(text, {}).get(target_lang, text)
    return {
        "success": True,
        "code": "OK",
        "data": {
            "original": text,
            "translated": translated,
            "target_lang": target_lang,
        },
    }

