# /models.py
from __future__ import annotations
from typing import Optional
from datetime import datetime
import uuid

from sqlmodel import SQLModel, Field


class Player(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    current_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PlayerAlias(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    player_id: str = Field(index=True, foreign_key="player.id")
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DiceSet(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    label: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Game(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None

    dice_set_id: Optional[str] = Field(default=None, foreign_key="diceset.id")
    notes: Optional[str] = None


class GamePlayer(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    game_id: str = Field(index=True, foreign_key="game.id")
    player_id: str = Field(index=True, foreign_key="player.id")

    turn_order: int
    display_name_snapshot: str
    joined_at: datetime = Field(default_factory=datetime.utcnow)


class Roll(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    game_id: str = Field(index=True, foreign_key="game.id")
    player_id: str = Field(index=True, foreign_key="player.id")

    total: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    idx_in_game: int


class FinalScore(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    game_id: str = Field(index=True, foreign_key="game.id")
    player_id: str = Field(index=True, foreign_key="player.id")

    score: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
