from fastapi import APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from . import models, schemas, repository, security


router = APIRouter()

@router.post("/token", response_model=schemas.Token)


@router.post("/users", response_model=schemas.User)


@router.get("/users/me", response_model=schemas.User)