from app.models.event import Event, EventParticipant, EventStatus
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
