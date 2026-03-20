from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass

from openai import OpenAI

from .schemas import DayAllocation, GameState


@dataclass
class Event:
    title: str
    text: str
    cash_impact: float


class FinanceGameEngine:
    def __init__(self) -> None:
        self._rng = random.Random()
        self._model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        api_key = os.getenv("OPENAI_API_KEY")
        self._client = OpenAI(api_key=api_key) if api_key else None

        self.gig_hourly = 22.0
        self.delivery_hourly = 24.0
        self.marketplace_hourly = 20.0

        self.gig_fee_rate = 0.18
        self.delivery_fee_rate = 0.12
        self.marketplace_fee_rate = 0.15

        self.tax_reserve_rate = 0.22

    def run_day(self, state: GameState, allocation: DayAllocation) -> dict:
        gross = (
            allocation.gig_hours * self.gig_hourly
            + allocation.delivery_hours * self.delivery_hourly
            + allocation.marketplace_hours * self.marketplace_hourly
        )

        platform_fees = (
            allocation.gig_hours * self.gig_hourly * self.gig_fee_rate
            + allocation.delivery_hours * self.delivery_hourly * self.delivery_fee_rate
            + allocation.marketplace_hours * self.marketplace_hourly * self.marketplace_fee_rate
        )

        variable_costs = 18.0 + (allocation.gig_hours + allocation.delivery_hours) * 2.8
        household_costs = self._daily_household_cost(state.day)

        taxable_base = max(0.0, gross - platform_fees)
        tax_reserve = taxable_base * self.tax_reserve_rate

        event = self._generate_event(state, allocation)

        net = gross - platform_fees - variable_costs - household_costs - tax_reserve + event.cash_impact

        state.cash += net
        state.tax_reserve += tax_reserve
        state.stress = self._next_stress(state, allocation, event)

        if state.cash < -400:
            state.status = "failed"
        elif state.day >= 30:
            state.status = "completed"
        else:
            state.day += 1

        return {
            "day": state.day,
            "gross_income": round(gross, 2),
            "platform_fees": round(platform_fees, 2),
            "variable_costs": round(variable_costs, 2),
            "household_costs": round(household_costs, 2),
            "tax_reserve": round(tax_reserve, 2),
            "event_title": event.title,
            "event_text": event.text,
            "event_cash_impact": round(event.cash_impact, 2),
            "end_cash": round(state.cash, 2),
        }

    def score(self, state: GameState) -> int:
        liquidity = min(35, max(0, int((state.cash + 400) / 80)))
        obligations = 25 if state.cash >= 0 else 10
        tax_plan = min(20, int(state.tax_reserve / 80))
        debt_pressure = 10 if state.debt <= 0 else max(0, 10 - int(state.debt / 200))
        volatility = max(0, 10 - int(state.stress / 12))
        return max(0, min(100, liquidity + obligations + tax_plan + debt_pressure + volatility))

    def _daily_household_cost(self, day: int) -> float:
        base = 92.0
        if day in {1, 15}:
            return base + 70.0
        if day in {5, 20}:
            return base + 120.0
        return base

    def _next_stress(self, state: GameState, allocation: DayAllocation, event: Event) -> int:
        work_hours = allocation.gig_hours + allocation.delivery_hours + allocation.marketplace_hours
        delta = 0
        if work_hours > 10:
            delta += 6
        elif work_hours < 5:
            delta += 2
        else:
            delta -= 1

        if event.cash_impact < -100:
            delta += 4
        if state.cash < 0:
            delta += 3

        return max(0, min(100, state.stress + delta))

    def _generate_event(self, state: GameState, allocation: DayAllocation) -> Event:
        if self._client is not None:
            ai_event = self._ai_event(state, allocation)
            if ai_event is not None:
                return ai_event
        return self._fallback_event(state)

    def _ai_event(self, state: GameState, allocation: DayAllocation) -> Event | None:
        try:
            prompt = {
                "city": state.city,
                "day": state.day,
                "cash": state.cash,
                "stress": state.stress,
                "allocation": allocation.model_dump(),
                "task": "Generate one realistic daily finance event for a U.S. gig worker household.",
                "constraints": {
                    "cash_impact_min": -180,
                    "cash_impact_max": 220,
                    "tone": "high school educational",
                    "return_json_only": True,
                    "json_schema": {
                        "title": "string",
                        "text": "string under 150 chars",
                        "cash_impact": "number",
                    },
                },
            }

            response = self._client.responses.create(
                model=self._model,
                input=[
                    {
                        "role": "system",
                        "content": "You output only valid JSON with keys title,text,cash_impact.",
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
            )
            raw = (response.output_text or "").strip()
            data = json.loads(raw)
            title = str(data.get("title", "Market Shift"))[:80]
            text = str(data.get("text", "A routine day with small changes."))[:150]
            impact = float(data.get("cash_impact", 0.0))
            impact = max(-180.0, min(220.0, impact))
            return Event(title=title, text=text, cash_impact=impact)
        except Exception:
            return None

    def _fallback_event(self, state: GameState) -> Event:
        roll = self._rng.random()
        if roll < 0.2:
            return Event(
                title="Vehicle Maintenance",
                text="Your car needs immediate maintenance before tomorrow's shifts.",
                cash_impact=-140.0,
            )
        if roll < 0.45:
            return Event(
                title="High Demand Window",
                text="A surge period paid better than expected across your platforms.",
                cash_impact=95.0,
            )
        if roll < 0.7:
            return Event(
                title="Return Request Spike",
                text="Multiple returns reduced your marketplace net payouts today.",
                cash_impact=-70.0,
            )
        return Event(
            title="Steady Day",
            text="No major surprises today. Your plan played out close to expected.",
            cash_impact=15.0,
        )
