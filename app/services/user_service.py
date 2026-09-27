from werkzeug.security import check_password_hash, generate_password_hash

from app.services.database import AnalysisJob, AppUser, BenchmarkModel, get_session_factory


def create_user(username, password, database_url=None):
    session_factory = get_session_factory(database_url)
    with session_factory.begin() as session:
        user = AppUser(
            username=username,
            password_hash=generate_password_hash(password),
        )
        session.add(user)
        session.flush()
        return {"id": user.id, "username": user.username}


def authenticate_user(username, password, database_url=None):
    session_factory = get_session_factory(database_url)
    with session_factory() as session:
        user = session.query(AppUser).filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return None
        return {"id": user.id, "username": user.username}


def transfer_guest_data(guest_key, user_id, database_url=None):
    """ログイン時に、このブラウザーのゲストデータをアカウントへ引き継ぐ。"""
    if not guest_key or not guest_key.startswith("guest:"):
        return

    account_key = f"user:{user_id}"
    session_factory = get_session_factory(database_url)
    with session_factory.begin() as session:
        for model in (AnalysisJob, BenchmarkModel):
            for row in session.query(model).all():
                if row.payload.get("owner_key") != guest_key:
                    continue
                row.payload = {
                    **row.payload,
                    "owner_key": account_key,
                    "owner_id": user_id,
                }
