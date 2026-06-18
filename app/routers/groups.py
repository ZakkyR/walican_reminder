import uuid
from fastapi import APIRouter, Request, Depends, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.friend_group import FriendGroup, FriendGroupMember
from app.models.user_guild import UserGuild
from app.models.bot_guild import BotGuild

router = APIRouter(prefix="/groups")
templates = Jinja2Templates(directory="app/templates")


def _require_group_owner(group_id: str, user: User, db: Session) -> FriendGroup:
    group = db.get(FriendGroup, group_id)
    if not group:
        raise HTTPException(status_code=404)
    if group.created_by != user.id:
        raise HTTPException(status_code=403)
    return group


def _require_group_member(group_id: str, user: User, db: Session) -> FriendGroup:
    group = db.get(FriendGroup, group_id)
    if not group:
        raise HTTPException(status_code=404)
    is_member = db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group_id,
        FriendGroupMember.user_id == user.id,
    ).first()
    if not is_member:
        raise HTTPException(status_code=403)
    return group



@router.get("", response_class=HTMLResponse)
async def list_groups(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    groups = (
        db.query(FriendGroup)
        .join(FriendGroupMember, FriendGroupMember.friend_group_id == FriendGroup.id)
        .filter(FriendGroupMember.user_id == user.id)
        .order_by(FriendGroup.created_at.desc())
        .all()
    )
    return templates.TemplateResponse("groups/list.html", {"request": request, "user": user, "groups": groups})


@router.post("")
async def create_group(name: str = Form(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = FriendGroup(name=name, created_by=user.id)
    db.add(group)
    db.flush()
    db.add(FriendGroupMember(friend_group_id=group.id, user_id=user.id))
    db.commit()
    return RedirectResponse(f"/groups/{group.id}", status_code=303)


@router.get("/{group_id}", response_class=HTMLResponse)
async def group_detail(group_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = _require_group_member(group_id, user, db)
    members = [m.user for m in group.members]
    is_owner = group.created_by == user.id
    user_guilds = db.query(UserGuild).join(BotGuild, BotGuild.guild_id == UserGuild.guild_id).filter(UserGuild.user_id == user.id).all()
    return templates.TemplateResponse("groups/detail.html", {
        "request": request, "user": user, "group": group,
        "members": members, "is_owner": is_owner,
        "user_guilds": user_guilds,
    })


@router.delete("/{group_id}")
async def delete_group(group_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = _require_group_owner(group_id, user, db)
    db.delete(group)
    db.commit()
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = "/groups"
    return response


@router.post("/{group_id}/members", response_class=HTMLResponse)
async def add_member(
    group_id: str,
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = _require_group_owner(group_id, user, db)

    name = name.strip()
    if not name or len(name) > 50:
        return HTMLResponse('<p style="color:#e55;margin-top:8px;">名前は1〜50文字で入力してください。</p>', status_code=200)

    # 登録ユーザーを Discord ユーザー名で検索
    target = db.query(User).filter(User.discord_username == name, User.is_guest == False).first()  # noqa: E712

    if not target:
        # 同名のゲストがすでに存在する場合は再利用
        target = db.query(User).filter(User.discord_username == name, User.is_guest == True).first()  # noqa: E712

    if not target:
        # 新規ゲストユーザーを作成
        guest_id = f"guest_{uuid.uuid4().hex}"
        target = User(
            discord_id=guest_id,
            discord_username=name,
            is_guest=True,
        )
        db.add(target)
        db.flush()

    exists = db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group_id,
        FriendGroupMember.user_id == target.id,
    ).first()
    if exists:
        return HTMLResponse(
            f'<p style="color:#e55;margin-top:8px;">「{name}」はすでにメンバーです。</p>',
            status_code=200,
        )

    db.add(FriendGroupMember(friend_group_id=group_id, user_id=target.id))
    db.commit()
    db.refresh(group)
    return templates.TemplateResponse(
        "groups/partials/member_row.html",
        {"request": request, "member": target, "group": group, "is_owner": True, "user": user},
    )


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(group_id: str, user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = _require_group_owner(group_id, user, db)
    # 自分自身はグループの最後のオーナーである場合は削除させない（任意）
    db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group_id,
        FriendGroupMember.user_id == user_id,
    ).delete()
    db.commit()
    return HTMLResponse("", status_code=200)
