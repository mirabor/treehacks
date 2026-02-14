"""Pydantic models for basket themes, preview, and API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Direction = Literal["BUY_YES", "BUY_NO", "SELL_YES", "SELL_NO"]

DIRECTION_OPTIONS: list[Direction] = ["BUY_YES", "BUY_NO", "SELL_YES", "SELL_NO"]


class BasketLeg(BaseModel):
    market_ticker: str
    event_ticker: str
    title: str
    direction: Direction = "BUY_YES"
    weight: float = Field(ge=0.0, le=1.0)
    enabled: bool = True


class BasketTheme(BaseModel):
    theme_id: str
    name: str
    description: str
    legs: list[BasketLeg]


class LegOverride(BaseModel):
    enabled: Optional[bool] = None
    direction: Optional[Direction] = None
    weight: Optional[float] = None


class GenerateRequest(BaseModel):
    query: str = Field(min_length=1)


class PreviewRequest(BaseModel):
    theme_id: str = ""  # ignored when theme is set
    total_budget_dollars: float = Field(gt=0)
    overrides: dict[str, LegOverride] = Field(default_factory=dict)
    theme: Optional[BasketTheme] = None  # when set, use this instead of theme_id lookup


class ExecuteRequest(BaseModel):
    theme_id: str = ""
    total_budget_dollars: float = Field(gt=0)
    overrides: dict[str, LegOverride] = Field(default_factory=dict)
    theme: Optional[BasketTheme] = None


class BasketOrderPreviewLeg(BaseModel):
    market_ticker: str
    title: str
    direction: Direction
    price_dollars: float
    contracts: int
    est_cost_dollars: float
    warnings: list[str] = Field(default_factory=list)


class BasketOrderPreview(BaseModel):
    total_budget_dollars: float
    legs: list[BasketOrderPreviewLeg]
    est_total_cost_dollars: float
    warnings: list[str] = Field(default_factory=list)


class BatchOrderResultLeg(BaseModel):
    market_ticker: str
    client_order_id: Optional[str] = None
    order_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


class ExecuteResponse(BaseModel):
    success: bool
    message: str
    legs: list[BatchOrderResultLeg] = Field(default_factory=list)
