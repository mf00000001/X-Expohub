"""团队 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_boss
from app.database.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.team import (
    TeamCreate,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
)
from app.services import team_service

router = APIRouter(prefix="/teams", tags=["团队"])


@router.post("/", response_model=ApiResponse[TeamResponse], status_code=201)
async def create_team(
    data: TeamCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_boss),
):
    """创建团队（老板）"""
    team = team_service.create_team(db, current_user.id, data)
    return ApiResponse(data=TeamResponse.model_validate(team))


@router.get("/", response_model=ApiResponse[list[TeamResponse]])
async def list_my_teams(
    db: Session = Depends(get_db),
    current_user=Depends(require_boss),
):
    """获取我的团队列表（老板）"""
    teams = team_service.get_boss_teams(db, current_user.id)
    result = []
    for team in teams:
        members = team_service.get_team_members(db, team.id)
        team_resp = TeamResponse.model_validate(team)
        team_resp.member_count = len(members)
        team_resp.members = [TeamMemberResponse.model_validate(m) for m in members]
        result.append(team_resp)
    return ApiResponse(data=result)


@router.get("/{team_id}", response_model=ApiResponse[TeamResponse])
async def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_boss),
):
    """获取团队详情（老板）"""
    team = team_service.get_team_by_id(db, team_id)
    members = team_service.get_team_members(db, team_id)
    team_resp = TeamResponse.model_validate(team)
    team_resp.member_count = len(members)
    team_resp.members = [TeamMemberResponse.model_validate(m) for m in members]
    return ApiResponse(data=team_resp)


@router.put("/{team_id}", response_model=ApiResponse[TeamResponse])
async def update_team(
    team_id: int,
    data: TeamUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_boss),
):
    """更新团队信息（老板）"""
    team = team_service.update_team(db, team_id, current_user.id, data)
    return ApiResponse(data=TeamResponse.model_validate(team))


@router.delete("/{team_id}", response_model=ApiResponse)
async def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_boss),
):
    """删除团队（老板）"""
    team_service.delete_team(db, team_id, current_user.id)
    return ApiResponse(message="团队已删除")


@router.post("/{team_id}/members", response_model=ApiResponse[TeamMemberResponse])
async def add_member(
    team_id: int,
    data: TeamMemberAdd,
    db: Session = Depends(get_db),
    current_user=Depends(require_boss),
):
    """添加团队成员（老板）"""
    member = team_service.add_member(
        db, team_id, current_user.id, data.user_id, data.role_in_team
    )
    return ApiResponse(data=TeamMemberResponse.model_validate(member))


@router.delete("/{team_id}/members/{user_id}", response_model=ApiResponse)
async def remove_member(
    team_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_boss),
):
    """移除团队成员（老板）"""
    team_service.remove_member(db, team_id, current_user.id, user_id)
    return ApiResponse(message="成员已移除")
