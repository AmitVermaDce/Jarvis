# Gold Price Demand Sensing Scenario — README

## Overview

This scenario uses Jarvis's multi-agent simulation engine to predict real-time gold price movements by modeling how different market participants react to and amplify market signals.

## How It Works

Jarvis creates a parallel digital world populated with AI agents representing real gold market participants — central bankers, investment bank analysts, ETF managers, gold traders, mining company executives, retail investors, financial journalists, and regulators. These agents interact on simulated social media platforms (Twitter + Reddit), creating emergent demand/supply signals that mirror real-world gold market dynamics.

## Seed Documents

| File | Description |
|---|---|
| `seed_gold_market_fundamentals.md` | Comprehensive gold market overview: price drivers, supply/demand factors, key market participants, demand sensing signals |
| `seed_gold_market_intelligence_april2026.md` | Real-time market intelligence: current prices, recent events, analyst forecasts, social media sentiment, forward demand signals |
| `seed_gold_behavioral_patterns.md` | Behavioral analysis of each market participant type: how they react, communicate, and influence gold prices through social media |

## Quick Start

### Option A: Use the Scenario Preset (Recommended)
1. Start Jarvis: `npm run dev`
2. Open `http://localhost:3000`
3. Click the **"Gold Price Demand Sensing"** preset on the home page
4. The seed files and simulation requirement are pre-loaded
5. Click **Start Engine** to begin

### Option B: Manual Upload
1. Start Jarvis: `npm run dev`
2. Open `http://localhost:3000`
3. Upload all 3 seed files from this folder
4. Enter the simulation requirement (see below)
5. Click **Start Engine**

## Simulation Requirement (Prompt)

Paste this into the "Simulation Requirement" field:

```
Simulate real-time gold market demand sensing and price prediction for April 2026. 
Model the interactions between central bank officials (Fed, PBOC, RBI), investment 
bank gold analysts (Goldman Sachs, JP Morgan, Citi), gold ETF managers, COMEX 
futures traders, gold mining company executives, retail gold investors, Indian 
and Chinese gold consumers, financial media reporters, and commodity regulators. 

Focus on how each participant reacts to and propagates the following current 
market signals: (1) PBOC's 17th consecutive month of gold buying, (2) US CPI 
coming in above expectations at 3.1%, (3) FOMC meeting minutes release, 
(4) approaching Indian Akshaya Tritiya festival demand, (5) gold ETF inflows 
at multi-year highs, (6) Iran nuclear negotiation breakdown.

Track how information flows between participants, how sentiment evolves, 
and predict the net demand trajectory (bullish/bearish/neutral) for gold 
over the next 1-4 weeks. Pay special attention to demand sensing signals: 
who amplifies bullish narratives, who provides contrarian views, and how 
retail investor FOMO develops or fades.
```

## Expected Agents (Auto-Generated)

Jarvis will generate ~10 entity types from the seed documents, likely including:

1. **CentralBanker** — Fed officials, PBOC representatives, RBI governors
2. **InvestmentBankAnalyst** — Goldman Sachs, JP Morgan, Citi commodity analysts
3. **ETFManager** — GLD/IAU fund managers, authorized participants
4. **CommodityTrader** — COMEX futures traders, London OTC market makers
5. **MiningExecutive** — Newmont, Barrick Gold, Agnico Eagle leadership
6. **RetailInvestor** — Individual gold investors, Reddit/WSB participants
7. **FinancialJournalist** — Bloomberg, Reuters, Kitco News reporters
8. **JewelryManufacturer** — Indian and Chinese jewelry industry representatives
9. **Person** — General public, opinion leaders (Peter Schiff, etc.)
10. **Organization** — Exchanges (COMEX, LBMA), regulators (CFTC, SEC)

## Interpreting Results

After simulation completes, use the **Report Agent** to analyze:

1. **Demand Trajectory**: Net bullish vs bearish sentiment evolution
2. **Key Influencers**: Which agents had the most impact on narrative direction
3. **Information Cascade**: How market signals propagated through the participant network
4. **Price Direction Prediction**: Based on agent consensus and demand signals
5. **Risk Scenarios**: What contrarian events could reverse the demand trajectory

## Tips for Best Results

- Start with 20-30 simulation rounds for a quick preview
- Use 40-60 rounds for more nuanced demand sensing patterns
- Interview specific agents post-simulation (e.g., ask the Goldman analyst about their price target rationale)
- Use the Report Agent to generate a "Demand Sensing Brief" for actionable insights
