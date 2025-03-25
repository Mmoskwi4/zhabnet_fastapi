from fastapi import Depends, HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer
from sqlalchemy.ext.asyncio import AsyncSession
from . import models, schemas, security
from .database import get_db
from kafka import KafkaProducer
import json
from decouple import config
from jose import jwt


oauth2_scheme = OAuth2AuthorizationCodeBearer(tokenUrl="token")

async def get_user(db: AsyncSession, username: str):
    result = await db.execute(models.User.__table__.select().where(models.User.username == username))
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user: schemas.UserCreated):
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    await db.flush()
    await db.commit()
    await db.refresh()

    try:
        producer = KafkaProducer(
            bootstrap_servers=config("KAFKA_BOOTSTRAP_SERVERS"),
            value_serializers=lambda v: json.dumps(v).encode("utf-8")
        )
        user_data = {"user_id": db_user.id, "username": db_user.username, "email": db_user.email}
        producer.send(config("KAFKA_TOPIC"), user_data)
        producer.flush()
        print(f"Отправлено сообщение user_created в Kafka: {user_data}")

    except Exception as e:
        print(f"Ошибка при отправке сообщенияв Kafka: {e}")
        await db.rollback()
        raise
    return db_user

async def authentication_user(db: AsyncSession, username: str, password: str):
    user = await get_user(db, username)
    if not user:
        return False
    if not security.verify_password(password, user.hashed_password):
        return False
    return user

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = {"username": username}
    except Exception as e:
        print(f"JWT Decode Error: {e}")
        raise credentials_exception
    user = await get_user(db, username=token_data["username"])
    if user is None:
        raise credentials_exception
    return user
         