"""API 請求模型（spec §10）。長度上限在這裡先擋一層（spec §3.6）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginReq(BaseModel):
    token: str = Field(min_length=1, max_length=64)


class DisplayNameReq(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=64)


class ChatMessage(BaseModel):
    # 只接受 user / assistant：client 不得注入 system 或 tool 訊息，
    # system prompt 一律由後端組（spec §8 單一事實來源）。
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatReq(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=128)
    messages: list[ChatMessage] | None = None
    document: str | None = Field(default=None, max_length=20000)


class SubmitFlagReq(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=128)
    flag: str = Field(min_length=1, max_length=200)


class XssCallbackReq(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=128)
    nonce: str = Field(min_length=1, max_length=128)


class HintReq(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=128)
    index: int = Field(ge=0, le=20)


class DefenseReq(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    system_prompt: str = Field(min_length=1, max_length=20000)


class AdminFinalReq(BaseModel):
    open: bool
