# Consumer Goods Demand Sensing Scenario — README

## Overview

This scenario uses Jarvis's multi-agent simulation engine to predict real-time shifts in consumer goods (FMCG/CPG) demand by modeling how different market participants — retailers, brands, consumers, analysts, and influencers — react to and amplify demand signals.

Unlike traditional demand forecasting that relies on historical sales patterns, this demand sensing approach captures the **emergent, social dynamics** that drive modern CPG markets: viral TikTok trends creating overnight demand spikes, GLP-1 drugs structurally reshaping snack consumption, inflation triggering private-label switching cascades, and weather events driving seasonal demand surges.

## How It Works

Jarvis creates a parallel digital world populated with AI agents representing real CPG market participants — brand executives, retail buyers, supply chain planners, consumer segments, social media influencers, commodity traders, market research analysts, and regulators. These agents interact on simulated social platforms (Twitter + Reddit), creating emergent demand signals that mirror real-world CPG dynamics.

## Seed Documents

| File | Description |
|---|---|
| `seed_consumer_goods_market_fundamentals.md` | CPG market structure, demand drivers (macro, social, weather, regulatory), key players across the value chain, and the demand sensing signal taxonomy |
| `seed_consumer_goods_market_intelligence_april2026.md` | Real-time market intelligence: current CPI/inflation, retailer announcements, CPG earnings data, GLP-1 impact metrics, TikTok trends, weather forecasts, and tariff developments |
| `seed_consumer_goods_behavioral_patterns.md` | Behavioral analysis of each participant type: how brand executives, retail buyers, consumers, influencers, and analysts react to and propagate demand signals |

## Quick Start

### Option A: Use the Scenario Preset (Recommended)
1. Start Jarvis: `npm run dev`
2. Open `http://localhost:3000`
3. Click the **"Consumer Goods Demand Sensing"** preset on the home page
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
Simulate real-time consumer goods demand sensing for April-May 2026 across the US 
FMCG/CPG market. Model the interactions between major CPG brand executives 
(Procter & Gamble, Unilever, Nestlé, PepsiCo, Coca-Cola), retail chain buyers 
(Walmart, Costco, Target, Amazon Fresh, Kroger), supply chain and logistics managers, 
consumer sentiment influencers (TikTok creators, health/wellness bloggers), market 
research analysts (Nielsen, IRI/Circana, Kantar), raw material commodity traders, 
FDA/regulatory officials, and everyday consumers across income segments.

Focus on how each participant reacts to and propagates the following current demand 
signals: (1) Sustained grocery inflation at 4.2% YoY driving private-label switching, 
(2) GLP-1 weight-loss drug adoption reshaping snack and beverage demand, 
(3) Summer 2026 heatwave forecasts boosting beverages and ice cream, 
(4) TikTok viral trend '#ProteinEverything' driving high-protein product demand, 
(5) Tariff increases on Chinese-manufactured packaging raising CPG costs, 
(6) Walmart announcing aggressive private-label expansion into premium organic.

Track how information flows between participants, how demand sentiment evolves across 
categories (snacks, beverages, personal care, household cleaning, packaged foods), 
and predict the net demand trajectory for the next 4-8 weeks. Pay special attention 
to demand sensing signals: early POS velocity changes, retailer order pattern shifts, 
social media trend acceleration, weather-driven demand spikes, and substitution 
effects from price sensitivity.
```

## Expected Agents (Auto-Generated)

Jarvis will generate ~12 entity types from the seed documents, likely including:

1. **CPGExecutive** — Brand leaders at P&G, PepsiCo, Coca-Cola, Unilever, Nestlé, General Mills, Mondelēz
2. **RetailBuyer** — Category managers and merchandising leads at Walmart, Costco, Target, Kroger, Amazon
3. **DemandPlanner** — Supply chain and forecasting professionals at CPG and retail companies
4. **MarketResearchAnalyst** — NielsenIQ, Circana, Kantar analysts who measure and narrate market trends
5. **TikTokInfluencer** — Food, fitness, and lifestyle creators driving product discovery and viral demand
6. **PriceSensitiveConsumer** — Budget-conscious shoppers switching to private label and discount retailers
7. **PremiumConsumer** — Higher-income shoppers focused on health, wellness, and premium products
8. **GenZConsumer** — Trend-driven young consumers discovering products through social media
9. **CommodityTrader** — Agricultural and packaging commodity traders signaling input cost changes
10. **FinancialJournalist** — Bloomberg, CNBC, Reuters reporters covering CPG industry and consumer trends
11. **RegulatoryOfficial** — FDA, USDA, FTC officials whose actions reshape product formulation and labeling
12. **DiscountRetailer** — Aldi, Dollar General, Lidl executives expanding to capture value-seeking consumers

## Key Demand Signals Being Tested

| # | Signal | Type | Expected Impact |
|---|---|---|---|
| 1 | Grocery inflation at 4.2% | Macro | Private-label switching accelerates; branded CPG volume pressure |
| 2 | GLP-1 drug adoption (24M users) | Structural | Snack/soda demand destruction; protein product demand creation |
| 3 | Summer heatwave forecast | Weather/Seasonal | Beverage and ice cream demand surge (15-25% uplift) |
| 4 | #ProteinEverything TikTok trend | Social/Viral | Protein-enriched product demand spike across categories |
| 5 | Packaging tariff increase | Cost/Policy | CPG price increases in Q3; accelerated reshoring |
| 6 | Walmart premium private-label push | Competitive | National brand share loss; category expansion for store brands |

## Interpreting Results

After simulation completes, use the **Report Agent** to analyze:

1. **Category Demand Trajectories**: Which categories are net bullish vs. bearish over 4-8 weeks
2. **Signal Propagation Speed**: How fast did each demand signal travel from origin to consumer behavior change
3. **Private Label vs. Branded Dynamics**: How did the inflation + Walmart private-label signals interact
4. **GLP-1 Demand Destruction Map**: Which categories and brands are most affected
5. **Viral Demand Amplification**: How did #ProteinEverything move from social media to retail shelves
6. **Weather-Demand Correlation**: How did the heatwave forecast change beverage/ice cream demand planning
7. **Cross-Signal Interaction**: Where do signals reinforce each other (e.g., inflation + private label) vs. conflict (e.g., premium protein trend vs. price sensitivity)

## Tips for Best Results

- Start with **25-35 simulation rounds** for a quick demand sensing overview
- Use **40-60 rounds** for deeper signal propagation analysis
- Interview specific agents post-simulation:
  - Ask the Walmart buyer: "How are you reallocating shelf space between branded and private label?"
  - Ask the PepsiCo executive: "What's your strategy to address GLP-1-driven volume decline?"
  - Ask the TikTok influencer: "What CPG products are you seeing trend next?"
- Use the Report Agent to generate a **"Weekly Demand Sensing Brief"** for actionable category-level predictions
