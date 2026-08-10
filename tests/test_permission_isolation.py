"""
ExpoHub 权限隔离测试（P0 核心）

这是整个测试方案中最关键的部分，验证四端路由隔离：
1. 游客只能访问游客端接口
2. 展商只能访问展商端接口
3. 主办方只能访问主办方端接口
4. 老板只能访问老板端接口
5. 未登录访问需认证接口返回 401
"""

import pytest
from fastapi import status


class TestVisitorAccess:
    """游客权限测试 - 游客只能访问公开接口和游客端接口"""

    def test_visitor_can_list_exhibitions(self, client, visitor_headers):
        """P0 测试：游客可以浏览展会列表（公开接口）"""
        response = client.get("/api/exhibitions", headers=visitor_headers)
        assert response.status_code == status.HTTP_200_OK

    def test_visitor_can_get_exhibition_detail(self, client, visitor_headers, sample_exhibition_published):
        """P0 测试：游客可以查看展会详情（公开接口）"""
        response = client.get(f"/api/exhibitions/{sample_exhibition_published.id}",
                            headers=visitor_headers)
        assert response.status_code == status.HTTP_200_OK

    def test_visitor_can_register_exhibition(self, client, visitor_headers, sample_exhibition_published):
        """P0 测试：游客可以报名展会"""
        response = client.post("/api/registrations", headers=visitor_headers, json={
            "exhibition_id": sample_exhibition_published.id,
            "is_registered": True,
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_visitor_can_favorite_exhibition(self, client, visitor_headers, sample_exhibition_published):
        """P1 测试：游客可以收藏展会"""
        response = client.post("/api/registrations", headers=visitor_headers, json={
            "exhibition_id": sample_exhibition_published.id,
            "is_favorite": True,
            "is_registered": False,
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_visitor_can_view_my_registrations(self, client, visitor_headers, sample_exhibition_published):
        """P1 测试：游客可以查看自己的报名列表"""
        # 先报名
        client.post("/api/registrations", headers=visitor_headers, json={
            "exhibition_id": sample_exhibition_published.id,
            "is_registered": True,
        })
        # 查看列表
        response = client.get("/api/registrations/my", headers=visitor_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1

    # ========== 游客禁止访问 ==========

    def test_visitor_cannot_create_exhibition(self, client, visitor_headers):
        """P0 测试：游客不能创建展会（主办方接口）→ 403"""
        response = client.post("/api/admin/exhibitions", headers=visitor_headers, json={
            "name": "Test Expo",
            "start_date": "2025-06-01T00:00:00Z",
            "end_date": "2025-06-05T00:00:00Z",
            "venue": "Venue",
            "address": "Address",
            "city": "City",
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_visitor_cannot_book_booth(self, client, visitor_headers, sample_booth):
        """P0 测试：游客不能预订展位（展商接口）→ 403"""
        response = client.post("/api/booths/book", headers=visitor_headers, json={
            "booth_id": sample_booth.id,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_visitor_cannot_approve_exhibition(self, client, visitor_headers, sample_exhibition_published):
        """P0 测试：游客不能审批展会（老板接口）→ 403"""
        response = client.post(
            f"/api/admin/exhibitions/{sample_exhibition_published.id}/approve",
            headers=visitor_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_visitor_cannot_view_stats(self, client, visitor_headers):
        """P1 测试：游客不能查看统计数据（老板/主办方接口）→ 403"""
        response = client.get("/api/admin/stats", headers=visitor_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_visitor_cannot_publish_exhibition(self, client, visitor_headers, sample_exhibition):
        """P1 测试：游客不能发布展会（主办方接口）→ 403"""
        response = client.post(
            f"/api/admin/exhibitions/{sample_exhibition.id}/publish",
            headers=visitor_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestExhibitorAccess:
    """展商权限测试"""

    def test_exhibitor_can_book_booth(self, client, exhibitor_headers, sample_booth):
        """P0 测试：展商可以预订展位"""
        response = client.post("/api/booths/book", headers=exhibitor_headers, json={
            "booth_id": sample_booth.id,
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "reserved"

    def test_exhibitor_can_list_booths(self, client, exhibitor_headers):
        """P1 测试：展商可以浏览展位列表"""
        response = client.get("/api/booths", headers=exhibitor_headers)
        assert response.status_code == status.HTTP_200_OK

    def test_exhibitor_can_view_exhibitions(self, client, exhibitor_headers):
        """P1 测试：展商可以浏览展会列表"""
        response = client.get("/api/exhibitions", headers=exhibitor_headers)
        assert response.status_code == status.HTTP_200_OK

    # ========== 展商禁止访问 ==========

    def test_exhibitor_cannot_create_exhibition(self, client, exhibitor_headers):
        """P0 测试：展商不能创建展会（主办方接口）→ 403"""
        response = client.post("/api/admin/exhibitions", headers=exhibitor_headers, json={
            "name": "Test Expo",
            "start_date": "2025-06-01T00:00:00Z",
            "end_date": "2025-06-05T00:00:00Z",
            "venue": "Venue",
            "address": "Address",
            "city": "City",
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_exhibitor_cannot_approve_exhibition(self, client, exhibitor_headers, sample_exhibition_published):
        """P0 测试：展商不能审批展会（老板接口）→ 403"""
        response = client.post(
            f"/api/admin/exhibitions/{sample_exhibition_published.id}/approve",
            headers=exhibitor_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_exhibitor_cannot_register_for_exhibition(self, client, exhibitor_headers, sample_exhibition_published):
        """P1 测试：展商不能报名展会（游客接口）→ 403"""
        response = client.post("/api/registrations", headers=exhibitor_headers, json={
            "exhibition_id": sample_exhibition_published.id,
            "is_registered": True,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_exhibitor_cannot_view_stats(self, client, exhibitor_headers):
        """P1 测试：展商不能查看全局统计（老板/主办方接口）→ 403"""
        response = client.get("/api/admin/stats", headers=exhibitor_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestOrganizerAccess:
    """主办方权限测试"""

    def test_organizer_can_create_exhibition(self, client, organizer_headers):
        """P0 测试：主办方可以创建展会"""
        response = client.post("/api/admin/exhibitions", headers=organizer_headers, json={
            "name": "New Expo by Organizer",
            "start_date": "2025-08-01T00:00:00Z",
            "end_date": "2025-08-05T00:00:00Z",
            "venue": "Shanghai Center",
            "address": "123 Shanghai Rd",
            "city": "Shanghai",
            "total_booths": 50,
        })
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "New Expo by Organizer"
        assert data["status"] == "draft"

    def test_organizer_can_update_own_exhibition(self, client, organizer_headers, sample_exhibition):
        """P0 测试：主办方可以更新自己的展会"""
        response = client.put(
            f"/api/admin/exhibitions/{sample_exhibition.id}",
            headers=organizer_headers,
            json={
                "name": "Updated Expo Name",
                "start_date": "2025-06-01T00:00:00Z",
                "end_date": "2025-06-05T00:00:00Z",
                "venue": "Shanghai Center",
                "address": "123 Shanghai Rd",
                "city": "Shanghai",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Updated Expo Name"

    def test_organizer_can_publish_exhibition(self, client, organizer_headers, sample_exhibition):
        """P0 测试：主办方可以发布展会"""
        response = client.post(
            f"/api/admin/exhibitions/{sample_exhibition.id}/publish",
            headers=organizer_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "published"

    def test_organizer_can_create_booth(self, client, organizer_headers, sample_exhibition):
        """P0 测试：主办方可以创建展位"""
        response = client.post("/api/admin/booths", headers=organizer_headers, json={
            "exhibition_id": sample_exhibition.id,
            "booth_number": "Z-001",
            "name": "VIP Booth",
            "area": 100.0,
            "price": 50000.0,
            "zone": "VIP区",
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["booth_number"] == "Z-001"

    def test_organizer_can_view_stats(self, client, organizer_headers):
        """P1 测试：主办方可以查看统计数据"""
        response = client.get("/api/admin/stats", headers=organizer_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_users" in data
        assert "total_exhibitions" in data

    # ========== 主办方禁止访问 ==========

    def test_organizer_cannot_approve_exhibition(self, client, organizer_headers, sample_exhibition_published):
        """P0 测试：主办方不能审批展会（老板接口）→ 403"""
        response = client.post(
            f"/api/admin/exhibitions/{sample_exhibition_published.id}/approve",
            headers=organizer_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_organizer_cannot_book_booth(self, client, organizer_headers, sample_booth):
        """P1 测试：主办方不能预订展位（展商接口）→ 403"""
        response = client.post("/api/booths/book", headers=organizer_headers, json={
            "booth_id": sample_booth.id,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_organizer_cannot_register_as_visitor(self, client, organizer_headers, sample_exhibition_published):
        """P1 测试：主办方不能报名展会（游客接口）→ 403"""
        response = client.post("/api/registrations", headers=organizer_headers, json={
            "exhibition_id": sample_exhibition_published.id,
            "is_registered": True,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestBossAccess:
    """老板权限测试"""

    def test_boss_can_approve_exhibition(self, client, boss_headers, sample_exhibition_published):
        """P0 测试：老板可以审批展会"""
        response = client.post(
            f"/api/admin/exhibitions/{sample_exhibition_published.id}/approve",
            headers=boss_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "ongoing"

    def test_boss_can_view_stats(self, client, boss_headers):
        """P0 测试：老板可以查看统计数据"""
        response = client.get("/api/admin/stats", headers=boss_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_users" in data
        assert "user_role_distribution" in data

    def test_boss_can_view_exhibitions(self, client, boss_headers):
        """P1 测试：老板可以浏览展会列表"""
        response = client.get("/api/exhibitions", headers=boss_headers)
        assert response.status_code == status.HTTP_200_OK

    # ========== 老板禁止访问 ==========

    def test_boss_cannot_create_exhibition(self, client, boss_headers):
        """P0 测试：老板不能创建展会（主办方接口）→ 403"""
        response = client.post("/api/admin/exhibitions", headers=boss_headers, json={
            "name": "Test Expo",
            "start_date": "2025-06-01T00:00:00Z",
            "end_date": "2025-06-05T00:00:00Z",
            "venue": "Venue",
            "address": "Address",
            "city": "City",
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_boss_cannot_book_booth(self, client, boss_headers, sample_booth):
        """P1 测试：老板不能预订展位（展商接口）→ 403"""
        response = client.post("/api/booths/book", headers=boss_headers, json={
            "booth_id": sample_booth.id,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_boss_cannot_register_as_visitor(self, client, boss_headers, sample_exhibition_published):
        """P1 测试：老板不能报名展会（游客接口）→ 403"""
        response = client.post("/api/registrations", headers=boss_headers, json={
            "exhibition_id": sample_exhibition_published.id,
            "is_registered": True,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_boss_cannot_publish_exhibition(self, client, boss_headers, sample_exhibition):
        """P1 测试：老板不能发布展会（主办方接口）→ 403"""
        response = client.post(
            f"/api/admin/exhibitions/{sample_exhibition.id}/publish",
            headers=boss_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestUnauthenticatedAccess:
    """未登录访问测试"""

    def test_unauthenticated_cannot_create_exhibition(self, client):
        """P0 测试：未登录不能创建展会 → 401"""
        response = client.post("/api/admin/exhibitions", json={
            "name": "Test",
            "start_date": "2025-06-01T00:00:00Z",
            "end_date": "2025-06-05T00:00:00Z",
            "venue": "V",
            "address": "A",
            "city": "C",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_book_booth(self, client, sample_booth):
        """P0 测试：未登录不能预订展位 → 401"""
        response = client.post("/api/booths/book", json={
            "booth_id": sample_booth.id,
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_register(self, client, sample_exhibition_published):
        """P0 测试：未登录不能报名展会 → 401"""
        response = client.post("/api/registrations", json={
            "exhibition_id": sample_exhibition_published.id,
            "is_registered": True,
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_approve(self, client, sample_exhibition_published):
        """P0 测试：未登录不能审批展会 → 401"""
        response = client.post(
            f"/api/admin/exhibitions/{sample_exhibition_published.id}/approve",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_view_stats(self, client):
        """P1 测试：未登录不能查看统计 → 401"""
        response = client.get("/api/admin/stats")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_update_profile(self, client):
        """P1 测试：未登录不能更新个人信息 → 401"""
        response = client.put("/api/users/me", json={"nickname": "hacker"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_can_list_exhibitions(self, client):
        """P1 测试：未登录可以浏览展会列表（公开接口）"""
        response = client.get("/api/exhibitions")
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_can_health_check(self, client):
        """P2 测试：未登录可以访问健康检查"""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
