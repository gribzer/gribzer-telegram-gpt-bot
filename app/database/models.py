# app/database/models.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, unique=True, nullable=False)
    selected_model = Column(String, nullable=True)
    instructions = Column(String, nullable=True)
    active_chat_id = Column(Integer, nullable=True)

    # Логика баланса, подписки, лимитов
    balance_tokens = Column(Float, default=0.0)
    free_requests_used = Column(Integer, default=0)
    free_requests_limit = Column(Integer, default=50)
    free_period_start = Column(DateTime, default=None)

    subscription_status = Column(Boolean, default=False)
    subscription_expired_at = Column(DateTime, default=None)

    # Пример связи 1->M (у одного User много Chats, если хотите)
    chats = relationship("Chat", back_populates="user")

class Chat(Base):
    __tablename__ = "user_chats"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False, default="Новый чат")
    is_favorite = Column(Boolean, default=False)

    user = relationship("User", back_populates="chats")
    messages = relationship("ChatMessage", back_populates="chat")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("user_chats.id"), nullable=False)
    role = Column(String, nullable=False)      # user / assistant / system
    content = Column(String, nullable=False)

    chat = relationship("Chat", back_populates="messages")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount_rub = Column(Float, default=0.0)
    tokens = Column(Float, default=0.0)
    payment_method = Column(String, nullable=True)  # 'T-Kassa', 'Telegram', ...
    status = Column(String, default="pending")      # 'pending', 'completed', ...
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    order_id = Column(String, nullable=True)        # "order-123"

    user = relationship("User")  # привязка к User
