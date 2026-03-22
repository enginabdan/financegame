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

        self.tax_reserve_rate = 0.22
        self._city_profiles = {
            "Charlotte, NC": {"income_mult": 1.00, "cost_mult": 1.00},
            "Raleigh, NC": {"income_mult": 1.02, "cost_mult": 1.05},
            "Atlanta, GA": {"income_mult": 1.06, "cost_mult": 1.12},
            "Nashville, TN": {"income_mult": 1.03, "cost_mult": 1.10},
            "Miami, FL": {"income_mult": 1.08, "cost_mult": 1.24},
            "Dallas, TX": {"income_mult": 1.04, "cost_mult": 1.09},
        }

    def run_day(self, state: GameState, allocation: DayAllocation) -> dict:
        work_hours = allocation.gig_hours + allocation.delivery_hours + allocation.marketplace_hours
        demand_mult = self._daily_demand_multiplier(state, work_hours)

        gig_hourly = 22.0 * self._city_income_multiplier(state.city) * demand_mult
        delivery_hourly = 24.0 * self._city_income_multiplier(state.city) * demand_mult
        marketplace_hourly = 20.0 * self._city_income_multiplier(state.city) * (1.0 + (demand_mult - 1.0) * 0.6)

        gross = (
            allocation.gig_hours * gig_hourly
            + allocation.delivery_hours * delivery_hourly
            + allocation.marketplace_hours * marketplace_hourly
        )

        gig_fee_rate = self._platform_fee_rate(base=0.18, stress=state.stress, kind="gig")
        delivery_fee_rate = self._platform_fee_rate(base=0.12, stress=state.stress, kind="delivery")
        marketplace_fee_rate = self._platform_fee_rate(base=0.15, stress=state.stress, kind="marketplace")

        platform_fees = (
            allocation.gig_hours * gig_hourly * gig_fee_rate
            + allocation.delivery_hours * delivery_hourly * delivery_fee_rate
            + allocation.marketplace_hours * marketplace_hourly * marketplace_fee_rate
        )

        variable_costs = 14.0 + (allocation.gig_hours + allocation.delivery_hours) * 3.4 + allocation.marketplace_hours * 1.4
        insurance_cost = self._insurance_cost(allocation.insurance_choice)
        emergency_contribution = allocation.emergency_fund_contribution
        car_action_cost = self._car_action_cost(allocation.car_action)
        household_costs = self._daily_household_cost(state.day) * self._city_cost_multiplier(state.city)

        taxable_base = max(0.0, gross - platform_fees)
        tax_reserve = taxable_base * self.tax_reserve_rate

        event = self._generate_event(state, allocation)
        debt_interest = state.debt * 0.0007
        debt_payment = 0.0
        if state.cash > 700 and state.debt > 0:
            debt_payment = min(45.0, state.debt, max(0.0, state.cash - 500))

        net = (
            gross
            - platform_fees
            - variable_costs
            - insurance_cost
            - emergency_contribution
            - car_action_cost
            - household_costs
            - tax_reserve
            + event.cash_impact
            - debt_interest
            - debt_payment
        )

        state.cash += net
        state.debt = max(0.0, state.debt + debt_interest - debt_payment)
        if state.cash < 0:
            debt_absorb = min(abs(state.cash), 120.0)
            state.debt += debt_absorb
            state.cash += debt_absorb
        state.tax_reserve += tax_reserve
        state.stress = self._next_stress(state, allocation, event)

        if state.cash < -400:
            state.status = "failed"
        elif state.day >= state.duration_days:
            state.status = "completed"
        else:
            state.day += 1

        event_text = event.text
        if debt_payment > 0:
            event_text = f"{event_text} Debt payment made: ${debt_payment:.0f}."
        if insurance_cost > 0:
            event_text = f"{event_text} Insurance: ${insurance_cost:.0f}."
        if emergency_contribution > 0:
            event_text = f"{event_text} Emergency fund set aside: ${emergency_contribution:.0f}."
        if car_action_cost > 0:
            event_text = f"{event_text} Car action cost: ${car_action_cost:.0f}."

        return {
            "day": state.day,
            "gross_income": round(gross, 2),
            "platform_fees": round(platform_fees, 2),
            "variable_costs": round(variable_costs, 2),
            "household_costs": round(household_costs, 2),
            "tax_reserve": round(tax_reserve, 2),
            "event_title": event.title,
            "event_text": event_text,
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
        base = 84.0
        if day in {1, 15}:
            return base + 80.0
        if day in {5, 20}:
            return base + 125.0
        if day in {10, 25}:
            return base + 55.0
        if day in {30}:
            return base + 160.0
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
        if event.cash_impact > 90:
            delta -= 2
        if state.cash < 0:
            delta += 3
        if state.debt > 400:
            delta += 2
        if allocation.insurance_choice == "none":
            delta += 2
        elif allocation.insurance_choice == "family":
            delta -= 1
        if allocation.car_action == "maintain":
            delta -= 1
        if allocation.car_action == "replace":
            delta -= 3
        if allocation.emergency_fund_contribution >= 40:
            delta -= 1

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
                "debt": state.debt,
                "tax_reserve": state.tax_reserve,
                "stress": state.stress,
                "allocation": allocation.model_dump(),
                "task": "Generate one realistic daily finance event for a U.S. gig worker household.",
                "constraints": {
                    "cash_impact_min": -180,
                    "cash_impact_max": 220,
                    "tone": "high school finance class, clear and practical",
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
        roll = self._rng.random() + (0.1 if state.stress > 70 else 0.0)
        if roll < 0.18:
            return Event(
                title="Vehicle Maintenance",
                text="Your car needs immediate maintenance before tomorrow's shifts.",
                cash_impact=-140.0,
            )
        if roll < 0.34:
            return Event(
                title="Slow Demand Block",
                text="Orders were slower than expected in your area for several hours.",
                cash_impact=-65.0,
            )
        if roll < 0.56:
            return Event(
                title="High Demand Window",
                text="A surge period paid better than expected across your platforms.",
                cash_impact=95.0,
            )
        if roll < 0.74:
            return Event(
                title="Return Request Spike",
                text="Multiple returns reduced your marketplace net payouts today.",
                cash_impact=-70.0,
            )
        if roll < 0.88:
            return Event(
                title="Repeat Customer Boost",
                text="One buyer placed a second order and improved your daily totals.",
                cash_impact=48.0,
            )
        return Event(
            title="Steady Day",
            text="No major surprises today. Your plan played out close to expected.",
            cash_impact=15.0,
        )

    def _city_income_multiplier(self, city: str) -> float:
        profile = self._city_profiles.get(city)
        return profile["income_mult"] if profile else 1.0

    def _city_cost_multiplier(self, city: str) -> float:
        profile = self._city_profiles.get(city)
        return profile["cost_mult"] if profile else 1.0

    def _daily_demand_multiplier(self, state: GameState, work_hours: int) -> float:
        # Keep day rhythm deterministic enough for teaching comparisons.
        weekday = (state.day - 1) % 7
        weekend_bonus = 0.08 if weekday in {5, 6} else 0.0
        underworked_penalty = -0.04 if work_hours < 5 else 0.0
        stress_penalty = -0.05 if state.stress > 75 else 0.0
        noise = self._rng.uniform(-0.05, 0.05)
        return max(0.82, min(1.20, 1.0 + weekend_bonus + underworked_penalty + stress_penalty + noise))

    def _platform_fee_rate(self, base: float, stress: int, kind: str) -> float:
        stress_delta = 0.01 if stress > 80 else 0.0
        kind_delta = 0.01 if kind == "marketplace" and stress > 65 else 0.0
        return max(0.08, min(0.30, base + stress_delta + kind_delta))

    def _insurance_cost(self, insurance_choice: str) -> float:
        if insurance_choice == "none":
            return 0.0
        if insurance_choice == "family":
            return 24.0
        return 12.0

    def _car_action_cost(self, car_action: str) -> float:
        if car_action == "maintain":
            return 18.0
        if car_action == "replace":
            return 160.0
        return 0.0


@dataclass
class StrategyOfferInternal:
    offer_id: str
    title: str
    text: str
    channel: str
    time_hours: float
    miles: float
    cash_in: float
    cash_out: float
    risk: str
    expected_profit: float


class StrategyAssignmentEngine:
    def __init__(self) -> None:
        self._rng = random.Random()
        self._model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        api_key = os.getenv("OPENAI_API_KEY")
        self._client = OpenAI(api_key=api_key) if api_key else None

    def build_day_offers(
        self,
        *,
        day: int,
        total_days: int,
        running_profit: float,
        previous_channels: list[str],
    ) -> tuple[str, list[StrategyOfferInternal]]:
        if self._client is not None:
            ai = self._ai_day_offers(
                day=day,
                total_days=total_days,
                running_profit=running_profit,
                previous_channels=previous_channels,
            )
            if ai is not None:
                return ai
        return self._fallback_day_offers(day=day, total_days=total_days)

    def _ai_day_offers(
        self,
        *,
        day: int,
        total_days: int,
        running_profit: float,
        previous_channels: list[str],
    ) -> tuple[str, list[StrategyOfferInternal]] | None:
        try:
            prompt = {
                "task": "Generate realistic same-day earning opportunities for a US gig worker and online seller.",
                "constraints": {
                    "count": 4,
                    "must_include_possible_channels": [
                        "Doordash",
                        "Walmart Spark",
                        "Amazon Delivery",
                        "Amazon Seller",
                        "Walmart Marketplace",
                        "Shopify",
                        "Etsy",
                        "eBay",
                        "Other",
                    ],
                    "offer_fields": [
                        "offer_id",
                        "title",
                        "text",
                        "channel",
                        "time_hours",
                        "miles",
                        "cash_in",
                        "cash_out",
                        "risk",
                        "expected_profit",
                    ],
                    "numbers": {
                        "time_hours_min": 0.5,
                        "time_hours_max": 6.0,
                        "miles_min": 0,
                        "miles_max": 140,
                        "cash_in_min": 20,
                        "cash_in_max": 450,
                        "cash_out_min": 2,
                        "cash_out_max": 220,
                        "expected_profit_min": -30,
                        "expected_profit_max": 260,
                    },
                    "return_json_only": True,
                },
                "context": {
                    "day": day,
                    "total_days": total_days,
                    "running_profit": running_profit,
                    "previous_channels": previous_channels[-6:],
                },
            }

            response = self._client.responses.create(
                model=self._model,
                input=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": json.dumps(prompt)},
                ],
            )
            raw = (response.output_text or "").strip()
            data = json.loads(raw)
            offers_raw = data.get("offers") or []
            brief = str(data.get("day_brief", f"Day {day}: New opportunities arrived.")).strip()[:220]
            offers = [self._sanitize_offer(item, idx) for idx, item in enumerate(offers_raw)]
            offers = [o for o in offers if o is not None]
            if len(offers) < 3:
                return None
            return brief, offers[:4]
        except Exception:
            return None

    def _fallback_day_offers(self, *, day: int, total_days: int) -> tuple[str, list[StrategyOfferInternal]]:
        channels = [
            ("Doordash", "Peak dinner window with stacked deliveries."),
            ("Walmart Spark", "Batch grocery run with moderate distance."),
            ("Amazon Delivery", "Last-mile route with fixed block payout."),
            ("Amazon Seller", "Restock + sponsored ad on winning SKU."),
            ("Walmart Marketplace", "Price optimization on two active listings."),
            ("Shopify", "Flash sale + email push to past customers."),
            ("Etsy", "Trending handmade keyword listing update."),
            ("eBay", "Auction flip with packaging and shipping cost."),
            ("TikTok Shop", "Short-form promo with affiliate split."),
            ("Local Wholesale", "Buy discounted pallet and relist online."),
        ]
        self._rng.shuffle(channels)
        offers: list[StrategyOfferInternal] = []
        for i, (channel, sentence) in enumerate(channels[:4], start=1):
            time_hours = round(self._rng.uniform(1.0, 5.5), 1)
            miles = round(self._rng.uniform(0, 120), 1 if self._rng.random() < 0.5 else 0)
            cash_in = round(self._rng.uniform(45, 320), 2)
            cash_out = round(self._rng.uniform(8, 170), 2)
            risk = self._rng.choice(["low", "medium", "high"])
            risk_penalty = {"low": 0.98, "medium": 0.9, "high": 0.78}[risk]
            expected_profit = round((cash_in - cash_out - miles * 0.22) * risk_penalty, 2)
            offers.append(
                StrategyOfferInternal(
                    offer_id=f"D{day}-{i}",
                    title=f"{channel} Opportunity",
                    text=sentence[:150],
                    channel=channel,
                    time_hours=time_hours,
                    miles=float(miles),
                    cash_in=cash_in,
                    cash_out=cash_out,
                    risk=risk,
                    expected_profit=expected_profit,
                )
            )
        brief = f"Day {day}/{total_days}: New demand and selling opportunities are available."
        return brief, offers

    def _sanitize_offer(self, item: dict, index: int) -> StrategyOfferInternal | None:
        try:
            offer_id = str(item.get("offer_id") or f"offer-{index+1}")[:24]
            title = str(item.get("title") or "Opportunity")[:120]
            text = str(item.get("text") or "A new earning option is available.")[:180]
            channel = str(item.get("channel") or "Other")[:60]
            time_hours = max(0.5, min(6.0, float(item.get("time_hours", 2.0))))
            miles = max(0.0, min(200.0, float(item.get("miles", 0.0))))
            cash_in = max(10.0, min(600.0, float(item.get("cash_in", 80.0))))
            cash_out = max(0.0, min(300.0, float(item.get("cash_out", 20.0))))
            risk = str(item.get("risk", "medium")).lower()
            if risk not in {"low", "medium", "high"}:
                risk = "medium"
            expected_profit = float(item.get("expected_profit", cash_in - cash_out - miles * 0.2))
            expected_profit = max(-50.0, min(320.0, expected_profit))
            return StrategyOfferInternal(
                offer_id=offer_id,
                title=title,
                text=text,
                channel=channel,
                time_hours=round(time_hours, 1),
                miles=round(miles, 1),
                cash_in=round(cash_in, 2),
                cash_out=round(cash_out, 2),
                risk=risk,
                expected_profit=round(expected_profit, 2),
            )
        except Exception:
            return None
