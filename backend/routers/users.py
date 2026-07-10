from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.database import register_user, login_user, get_or_create_user

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str = ""  # 可选，兼容旧版无密码


@router.post("/register")
def register(req: RegisterRequest):
    """注册新用户"""
    if len(req.username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少2个字符")
    if len(req.password) < 3:
        raise HTTPException(status_code=400, detail="密码至少3个字符")

    user_id = register_user(req.username, req.password)
    if user_id is None:
        raise HTTPException(status_code=409, detail="用户名已存在，请换一个")
    return {"user_id": user_id, "username": req.username, "message": "注册成功"}


@router.post("/login")
def login(req: LoginRequest):
    """用户登录"""
    if not req.username:
        raise HTTPException(status_code=400, detail="请输入用户名")

    if req.password:
        # 密码登录
        user_id = login_user(req.username, req.password)
        if user_id is None:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        return {"user_id": user_id, "username": req.username}
    else:
        # 兼容旧版无密码登录
        user_id = get_or_create_user(req.username)
        return {"user_id": user_id}
