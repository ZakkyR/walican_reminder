from app.models.user_guild import UserGuild


def test_user_guild_creation(db, user):
    guild = UserGuild(user_id=user.id, guild_id="111222333444555666", guild_name="Test Server")
    db.add(guild)
    db.commit()
    db.refresh(guild)
    assert guild.user_id == user.id
    assert guild.guild_id == "111222333444555666"
    assert guild.guild_name == "Test Server"
