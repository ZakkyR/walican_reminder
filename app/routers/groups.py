from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.friend_group import FriendGroup, FriendGroupMember

router = APIRouter(prefix="/groups")
templates = Jinja2Templates(directory="app/templates")


def _require_group_owner(group_id: str, user: User, db: Session) -> FriendGroup:
    group = db.get(FriendGroup, group_id)
    if not group or group.created_by != user.id:
        raise HTTPException(status_code=404)
    return group


@router.get("", response_class=HTMLResponse)
async def list_groups(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    groups = db.query(FriendGroup).filter(FriendGroup.created_by == user.id).all()
    return templates.TemplateResponse("groups/list.html", {"request": request, "user": user, "groups": groups})


@router.post("")
async def create_group(name: str = Form(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = FriendGroup(name=name, created_by=user.id)
    db.add(group)
    db.commit()
    return RedirectResponse(f"/groups/{group.id}", status_code=303)


@router.get("/{group_id}", response_class=HTMLResponse)
async def group_detail(group_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = _require_group_owner(group_id, user, db)
    members = [m.user for m in group.members]
    return templates.TemplateResponse("groups/detail.html", {"request": request, "user": user, "group": group, "members": members})


@router.post("/{group_id}/members", response_class=HTMLResponse)
async def add_member(group_id: str, request: Request, username: str = Form(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = _require_group_owner(group_id, user, db)
    target = db.query(User).filter(User.discord_username == username).first()
    if not target:
        return HTMLResponse(
            f'<p class="text-danger">ユーザー「{username}」は見つかりません（一度でもログインしている必要があります）</p>',
            status_code=200,
        )
    exists = db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group_id,
        FriendGroupMember.user_id == target.id,
    ).first()
    if not exists:
        db.add(FriendGroupMember(friend_group_id=group_id, user_id=target.id))
        db.commit()
    db.refresh(group)
    return templates.TemplateResponse(
        "groups/partials/member_row.html",
        {"request": request, "member": target, "group": group},
    )


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(group_id: str, user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_group_owner(group_id, user, db)
    db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group_id,
        FriendGroupMember.user_id == user_id,
    ).delete()
    db.commit()
    return HTMLResponse("", status_code=200)
