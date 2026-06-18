from app.models.friend_group import FriendGroup, FriendGroupMember


def test_create_group(auth_client, db, user):
    response = auth_client.post("/groups", data={"name": "旅行仲間"}, follow_redirects=False)
    assert response.status_code in (302, 303)
    group = db.query(FriendGroup).filter(FriendGroup.name == "旅行仲間").first()
    assert group is not None
    assert group.created_by == user.id
    # 作成者が自動的にメンバーに追加されていることを確認
    member = db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group.id,
        FriendGroupMember.user_id == user.id,
    ).first()
    assert member is not None


def test_add_member_to_group(auth_client, db, user):
    from app.models.user import User
    other = User(discord_id="999", discord_username="OtherUser")
    db.add(other)
    group = FriendGroup(name="Test", created_by=user.id)
    db.add(group)
    db.commit()
    db.refresh(group)

    response = auth_client.post(f"/groups/{group.id}/members", data={"name": "OtherUser"}, follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    member = db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group.id,
        FriendGroupMember.user_id == other.id,
    ).first()
    assert member is not None


def test_delete_member(auth_client, db, user):
    from app.models.user import User
    other = User(discord_id="888", discord_username="ToDelete")
    db.add(other)
    group = FriendGroup(name="Test2", created_by=user.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    db.refresh(other)
    member = FriendGroupMember(friend_group_id=group.id, user_id=other.id)
    db.add(member)
    db.commit()

    response = auth_client.delete(f"/groups/{group.id}/members/{other.id}", follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    assert db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group.id,
        FriendGroupMember.user_id == other.id,
    ).first() is None
