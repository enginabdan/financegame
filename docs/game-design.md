# Game Design: Hustle & Home: Charlotte 30

## Audience

- U.S. high school personal finance classes
- Grade band: 9-12

## Game Loop

Each in-game day, the player:

1. Reviews current cash, obligations, and risk flags.
2. Chooses time allocation across income channels.
3. Handles household/business events.
4. Sees net daily impact and updated financial position.

The simulation runs for 30 in-game days.

## Income Channels

- Gig driving shifts
- Delivery block shifts
- Marketplace sales operations

Each channel has:

- Gross income potential
- Variable cost exposure (fuel, returns, packing, etc.)
- Platform commissions/fees
- Taxable earnings

## Expense Model

Recurring:

- Rent
- Utilities
- Groceries
- Insurance
- Child expenses

Variable/random:

- Car repairs
- Medical out-of-pocket
- Penalties/late fees
- Marketplace return losses

## Tax & Fee Layer (MVP)

- Flat estimated self-employment reserve percentage
- Platform-specific commission rates
- Basic monthly tax reserve scoring

## Win Condition

Primary objective:

- Finish day 30 solvent (non-negative cash) and with strong stability score

Secondary objectives:

- Build emergency reserve
- Avoid high-interest debt traps
- Maintain healthy work-life pressure index

## Scoring (MVP)

Composite score out of 100:

- 35: Liquidity/Cash resilience
- 25: Obligation management (on-time essentials)
- 20: Tax/fee planning
- 10: Debt pressure control
- 10: Volatility management

## AI Event System

AI generates realistic day events based on:

- Current city
- Household profile
- Work mix decisions
- Existing stressors and missed obligations

Events include:

- Positive opportunity (high-demand shift, bulk order)
- Neutral friction (delays, small fee adjustments)
- Negative shock (car issue, platform suspension risk)

## Classroom Use

- Individual play: 20-40 minutes
- Group debrief: decision tradeoff discussion
- Reflection prompts:
  - What looked profitable but was costly after fees?
  - Which fixed costs dominated your strategy?
  - What safety margin is enough for uncertainty?
