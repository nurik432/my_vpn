from sqlalchemy import select
from datetime import datetime

from database import AsyncSessionLocal
from database.models import User, Subscription
from services.marzban import MarzbanAPI

async def sync_users_from_marzban(marzban: MarzbanAPI):
    marzban_users = await marzban.get_all_users()
    print(f"🔄 Резервная синхронизация: найдено {len(marzban_users)} ключей в Marzban.")
    
    async with AsyncSessionLocal() as db_session:
        restored = 0
        for m_user in marzban_users:
            username = m_user.get("username")
            if not username or not username.startswith("tg_"):
                continue
                
            parts = username.split("_")
            if len(parts) >= 2:
                try:
                    tg_id = int(parts[1])
                except ValueError:
                    continue
                    
                result = await db_session.execute(select(User).where(User.id == tg_id))
                user = result.scalar_one_or_none()
                
                expire_ts = m_user.get("expire", 0) or 0
                expire_dt = datetime.fromtimestamp(expire_ts) if expire_ts > 0 else datetime.now()
                
                if not user:
                    user = User(
                        id=tg_id,
                        full_name=f"User {tg_id}",
                        username=None,
                        marzban_username=username,
                        trial_used=True
                    )
                    db_session.add(user)
                    db_session.add(Subscription(
                        user_id=tg_id, plan="trial", days=3, expires_at=expire_dt
                    ))
                    restored += 1
                else:
                    if not user.marzban_username:
                        user.marzban_username = username
                        user.trial_used = True
                        db_session.add(Subscription(
                            user_id=tg_id, plan="trial", days=3, expires_at=expire_dt
                        ))
                        restored += 1
        
        if restored > 0:
            await db_session.commit()
            print(f"✅ Успешно восстановлен доступ для {restored} пользователей!")
