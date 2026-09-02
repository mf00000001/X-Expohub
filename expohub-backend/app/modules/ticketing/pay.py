"""
支付抽象（P3）

- PayProvider: 统一支付接口（create_payment）
- MockPayProvider: 开发/演示用 Mock，直接返回支付成功
  （后续接入微信支付时新增 WechatPayProvider，业务代码不变）

金额单位：分。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional


class PayProvider(ABC):
    """支付渠道抽象"""

    name: str = "abstract"

    @abstractmethod
    def create_payment(self, order_no: str, amount_cents: int, subject: str) -> dict:
        """
        发起支付。

        返回统一结构:
        {
            "provider": 渠道名,
            "pay_params": 前端唤起支付所需参数(dict),
            "paid": 是否已支付成功(Mock 直接成功；真实渠道需回调确认),
        }
        """


class MockPayProvider(PayProvider):
    """Mock 支付：发起即支付成功（演示/联调用）"""

    name = "mock"

    def create_payment(self, order_no: str, amount_cents: int, subject: str) -> dict:
        return {
            "provider": self.name,
            "pay_params": {
                "mock_order_no": order_no,
                "mock_amount_cents": amount_cents,
                "mock_subject": subject,
                "notice": "Mock 支付渠道：联调/演示用，发起即成功",
            },
            "paid": True,
            "paid_at": datetime.now(timezone.utc).isoformat(),
        }


# 渠道注册表（新增渠道时在此登记）
PAY_PROVIDERS: dict[str, PayProvider] = {
    MockPayProvider.name: MockPayProvider(),
}


def get_pay_provider(method: str) -> Optional[PayProvider]:
    """按支付方式获取渠道实例（未知渠道返回 None）"""
    return PAY_PROVIDERS.get(method)
