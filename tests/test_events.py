from app.models.event import Event, EventParticipant, EventStatus
from app.models.notification import NotificationSetting, NotificationMode
from app.models.user import User

def test_create_event(auth_client, db, user):
    response = auth_client.post("/events", data={
        "name": "北海道旅行",
        "description": "2025年夏",
        "payment_deadline": "2025-08-31",
        "participant_ids": [user.id],
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    event = db.query(Event).filter(Event.name == "北海道旅行").first()
    assert event is not None
    assert db.query(EventParticipant).filter(EventParticipant.event_id == event.id).count() == 1

def test_create_event_with_friend_group(auth_client, db, user):
    from app.models.friend_group import FriendGroup, FriendGroupMember
    other = User(discord_id="777", discord_username="GroupUser")
    db.add(other)
    group = FriendGroup(name="旅行仲間", created_by=user.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    db.refresh(other)
    db.add(FriendGroupMember(friend_group_id=group.id, user_id=other.id))
    db.commit()

    response = auth_client.post("/events", data={
        "name": "グループイベント",
        "friend_group_id": group.id,
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    event = db.query(Event).filter(Event.name == "グループイベント").first()
    participants = db.query(EventParticipant).filter(EventParticipant.event_id == event.id).all()
    participant_ids = {p.user_id for p in participants}
    assert user.id in participant_ids
    assert other.id in participant_ids

def test_add_participant_to_event(auth_client, db, user):
    event = Event(name="参加者追加テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    other = User(discord_id="p001", discord_username="NewParticipant")
    db.add(other)
    db.commit()
    db.refresh(event)

    response = auth_client.post(f"/events/{event.id}/participants", data={"name": "NewParticipant"}, follow_redirects=False)
    assert response.status_code == 200
    assert db.query(EventParticipant).filter(
        EventParticipant.event_id == event.id,
        EventParticipant.user_id == other.id,
    ).first() is not None


def test_add_guest_participant_to_event(auth_client, db, user):
    event = Event(name="ゲスト追加テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.commit()
    db.refresh(event)

    response = auth_client.post(f"/events/{event.id}/participants", data={"name": "山田太郎"}, follow_redirects=False)
    assert response.status_code == 200
    guest = db.query(User).filter(User.discord_username == "山田太郎", User.is_guest == True).first()  # noqa: E712
    assert guest is not None
    assert db.query(EventParticipant).filter(
        EventParticipant.event_id == event.id,
        EventParticipant.user_id == guest.id,
    ).first() is not None


def test_remove_participant_from_event(auth_client, db, user):
    event = Event(name="削除テスト", created_by=user.id)
    db.add(event)
    other = User(discord_id="p002", discord_username="ToRemove")
    db.add(other)
    db.commit()
    db.refresh(event)
    db.refresh(other)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.add(EventParticipant(event_id=event.id, user_id=other.id))
    db.commit()

    response = auth_client.delete(f"/events/{event.id}/participants/{other.id}", follow_redirects=False)
    assert response.status_code == 200
    assert db.query(EventParticipant).filter(
        EventParticipant.event_id == event.id,
        EventParticipant.user_id == other.id,
    ).first() is None


def test_cannot_remove_creator_from_event(auth_client, db, user):
    event = Event(name="作成者削除不可テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.commit()
    db.refresh(event)

    response = auth_client.delete(f"/events/{event.id}/participants/{user.id}", follow_redirects=False)
    assert response.status_code == 400


def test_delete_event_with_notification_setting(auth_client, db, user):
    event = Event(name="通知付き削除テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.flush()
    db.add(NotificationSetting(
        event_id=event.id,
        discord_channel_id="111",
        mode=NotificationMode.scheduled,
        schedule_cron="0 12 * * 1",
    ))
    db.commit()
    db.refresh(event)

    response = auth_client.delete(f"/events/{event.id}", follow_redirects=False)
    assert response.status_code in (200, 204, 302, 303)
    assert db.query(Event).filter(Event.id == event.id).first() is None
    assert db.query(NotificationSetting).filter(NotificationSetting.event_id == event.id).first() is None


def test_complete_event(auth_client, db, user):
    event = Event(name="完了テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.commit()
    db.refresh(event)

    response = auth_client.post(f"/events/{event.id}/complete", follow_redirects=False)
    assert response.status_code in (302, 303)
    db.refresh(event)
    assert event.status == EventStatus.completed
