# Saudi P&C Risk Model UI Guide

This guide explains every major data point shown in the web app in plain language. It is written for someone who does not work in insurance.

The app is a prototype for deciding whether an insurance company should offer a price for a property and casualty insurance request in Saudi Arabia. Property and casualty, often shortened to P&C, means insurance for things like vehicles, buildings, construction projects, cargo, and liability claims.

The app has nine main tabs:

1. Underwriting
2. Data
3. Actuarial
4. Model Diagnostics
5. Reserving
6. Capital
7. Scenarios
8. Rules
9. Proxy Factors

There is also a sidebar called Model Run.

## Common Terms

| Term | Plain-English meaning |
|---|---|
| SAR | Saudi Riyal, the currency used throughout the app. |
| Policy | An insurance contract or quote request. |
| Portfolio | A collection of many insurance policies. |
| Line of business, or LOB | The type of insurance, such as Motor or Property & Fire. |
| Premium | The price charged to the customer for insurance. |
| Claim | A request for payment after a covered loss. |
| Expected loss | The model's estimate of how much claims will cost on average. |
| Limit | The maximum amount the insurer may have to pay for a covered loss. |
| Deductible | The amount the customer pays before insurance starts paying. |
| Reinsurance | Insurance bought by the insurance company to share very large losses with another insurer. |
| Ceded share | The percentage of risk passed to reinsurers. |
| Capital | Money the insurer must hold aside to survive unusually bad outcomes. |
| SCR | Solvency Capital Requirement. In this app it means a proxy estimate of capital needed for a risk. |
| RBC | Risk-Based Capital. A solvency framework where capital depends on how risky the insurer's business is. |
| Cat | Short for catastrophe, meaning major events like flood, storm, fire, or explosion. |
| Requires review | The app will not auto-quote. A human specialist must approve or change the terms. |
| Decline | The app says the risk is outside current appetite and should not be offered as entered. |
| Appetite | The insurer's current willingness to accept a risk. |

## Sidebar: Model Run

The sidebar controls the data and model run used by the app.

| Data point | What it means | Why it matters |
|---|---|---|
| Data rows | The number of generated portfolio records used to train the baseline model and populate dashboard views. | More rows give the model more examples, but the app may take longer to load. |
| Random seed | A number that makes the generated data repeatable. | If you use the same seed and row count, the app should produce the same portfolio data again. This is useful for demonstrations and testing. |
| Scenario | The stress or base case used to generate the data feeds and capital results. Examples include Base, High Inflation, Severe Flood Year, and Reinsurer Downgrade/Default. | It lets you see how pricing, reserves, and capital move under different assumptions. |
| Prototype notice | A reminder that the app uses generated portfolio data and proxy RBC factors, not final regulatory calibration. | It prevents users from treating prototype outputs as regulatory or production pricing decisions. |

## Tab 1: Underwriting

The Underwriting tab is the main quote screen. You enter a policy request, and the app returns a decision: Quote, Requires Review, or Decline.

### Main Policy Inputs

These fields appear for every line of business.

| Data point | What it means | Why it matters |
|---|---|---|
| Line of business | The type of insurance being requested. Options are Motor, Property & Fire, Engineering & Construction, Marine & Cargo, and Casualty/Liability. | Different insurance types have different risk patterns, pricing assumptions, catastrophe exposure, and appetite limits. |
| Region | The Saudi region or market area where the risk is located or mainly operates. | The model uses region to adjust for traffic density, flood exposure, sandstorm exposure, industrial concentration, and logistics exposure. |
| Reinsurer rating | The credit quality of the reinsurer supporting the policy, such as AAA, AA, A, BBB, BB, or Unrated. | A weak or unrated reinsurer may not pay when needed, so the model increases counterparty concern. |
| Exposure value | The value or scale of the thing being insured. For a building, this may be the property value. For cargo, it may be the shipment value. For liability, it may be linked to company size. | Higher exposure means there is more value at risk. It also affects catastrophe load and capital. |
| Coverage limit | The maximum amount the insurer may pay under the policy. | A high limit can push a risk outside appetite even if expected claims look manageable. |
| Deductible | The amount the insured customer pays before the insurer pays. | A larger deductible means the customer absorbs smaller losses, which can reduce insurer risk. |
| Term | How long the policy lasts, usually 6, 12, 18, or 24 months. | Longer terms expose the insurer to possible losses for more time. |
| Prior claims, 3Y | Number of claims in the past three years. | A history of claims can suggest higher future risk. |
| Risk controls | A 0 to 100 score for risk management quality. Higher is better. | Strong controls, such as fire protection or safety procedures, reduce the chance or size of loss. |
| Reinsurance ceded | The percentage of risk passed to a reinsurer. | Ceding risk can reduce net loss, but very high cession creates dependence on reinsurer credit quality. |
| Event accumulation | A 0 to 100 score for how much one event could affect many insured items at once. | High accumulation can mean one flood, fire, explosion, or project incident causes many claims together. |

### Motor-Specific Inputs

These fields appear when Line of business is Motor.

| Data point | What it means | Why it matters |
|---|---|---|
| Policy type | Comprehensive or Compulsory. Comprehensive covers broader damage; compulsory is usually third-party liability. | Broader cover usually means more ways for claims to happen. |
| Vehicle class | Type of vehicle, such as private car, SUV, taxi/ride-hailing, light commercial, or heavy truck. | Commercial and heavy vehicles usually have higher claim frequency and severity. |
| Driver age | Age of the main driver. | Very young drivers are often treated as higher risk. |
| Vehicle age | Age of the vehicle in years. | Older vehicles may have higher repair or breakdown-related claim costs. |
| Fleet size | Number of vehicles covered. | More vehicles means more exposure and a higher chance that at least one has a claim. |

### Property & Fire-Specific Inputs

These fields appear when Line of business is Property & Fire.

| Data point | What it means | Why it matters |
|---|---|---|
| Occupancy | How the property is used, such as residential, retail, warehouse, manufacturing, or petrochemical support. | Some uses are more hazardous than others. A warehouse or industrial property may have more fire or accumulation risk than a home. |
| Fire protection | A 0 to 100 score for fire defenses such as sprinklers, alarms, hydrants, and procedures. Higher is better. | Better fire protection can reduce both the chance and severity of fire losses. |
| Construction quality | A 0 to 100 score for building quality and resilience. Higher is better. | Better construction can reduce damage from fire, flood, wind, or operational hazards. |
| Hazard score | A 0 to 100 score for inherent property hazard. Higher means riskier. | This captures how dangerous the property use is before considering controls. |

### Engineering & Construction-Specific Inputs

These fields appear when Line of business is Engineering & Construction.

| Data point | What it means | Why it matters |
|---|---|---|
| Project type | Type of construction project, such as civil works, renewables, rail, industrial plant, or giga-project package. | Complex infrastructure and industrial projects can have large losses and delays. |
| Duration | Project length in months. | Longer projects have more time for accidents, delays, storms, or cost overruns. |
| Contractor experience | Years of experience of the contractor. | More experienced contractors are assumed to manage risk better. |
| Complexity score | A 0 to 100 score for technical project difficulty. Higher means harder. | More complex projects can have larger and less predictable losses. |

### Marine & Cargo-Specific Inputs

These fields appear when Line of business is Marine & Cargo.

| Data point | What it means | Why it matters |
|---|---|---|
| Cargo type | Type of goods being transported, such as general cargo, electronics, cold chain, project cargo, or hazardous cargo. | Fragile, temperature-sensitive, oversized, or hazardous cargo can be riskier. |
| Transit distance | Distance the cargo travels, in kilometers. | Longer routes give more opportunity for accidents, theft, spoilage, or delays. |
| Storage days | Number of days cargo is stored during the journey. | More storage time can increase damage, theft, or accumulation risk. |
| Cargo risk | A 0 to 100 score for the inherent risk of the cargo. Higher means riskier. | This summarizes cargo sensitivity, value concentration, and handling difficulty. |

### Casualty/Liability-Specific Inputs

These fields appear when Line of business is Casualty/Liability.

| Data point | What it means | Why it matters |
|---|---|---|
| Liability type | Type of liability cover, such as general liability, professional indemnity, D&O, or product liability. | Different liability covers have different lawsuit and settlement patterns. |
| Annual revenue | The insured company's yearly revenue. | Larger companies may face larger claims because they have more operations, customers, contracts, or public exposure. |
| Limit intensity | A 0 to 100 score for how large the requested limit is relative to company size. | High limits relative to company size may indicate unusual protection needs or high severity potential. |
| Professional risk | A 0 to 100 score for professional or management-related risk. | Higher values mean greater chance of errors, negligence allegations, management disputes, or professional claims. |

### Underwriting Decision Outputs

These appear after the app evaluates the request.

| Data point | What it means | Why it matters |
|---|---|---|
| Decision badge | Quote, Requires Review, or Decline. | This is the main answer from the app. Quote means offer a premium. Requires Review means human approval is needed. Decline means the entered terms are outside current appetite. |
| Offered premium | The rounded premium the app would offer if the decision is Quote or Refer. If Decline, it says Not offered. | This is the price shown to the underwriter. |
| Risk score | A 0 to 100 score summarizing the overall risk. Higher is riskier. | It combines probability of claim, loss size, capital strain, catastrophe load, accumulation, controls, prior claims, and limit intensity. |
| Expected loss | Average claim cost the model expects for this policy. | This is the core cost of insurance before expenses, profit, catastrophe loading, and capital cost. |
| SCR impact | Proxy capital required for this policy. | A policy can be profitable on average but still require a lot of capital because bad outcomes could be large. |

### Premium Chart and Premium Table

The Premium chart and table break the price into pieces.

| Component | What it means | Plain-English interpretation |
|---|---|---|
| Expected loss | The average claim cost expected from the policy. | The insurer's estimated cost of paying claims. |
| Cat load | Extra charge for catastrophe-type events such as flood, sandstorm, large fire, explosion, or project clash event. | A buffer for rare but damaging events. |
| Capital load | Charge for tying up insurer capital. | The insurer must hold capital to support the risk, and that capital has a cost. |
| Expense load | Operating cost allowance. | Covers expenses such as underwriting, administration, systems, commissions, and service. |
| Profit margin | Target profit allowance. | The margin the insurer wants above claims, expenses, and capital cost. |
| Technical premium | The calculated price before final market or commercial adjustment. | The model's pure technical view of what should be charged. |

### Capital Section in the Underwriting Tab

| Data point | What it means | Why it matters |
|---|---|---|
| Underwriting capital | Capital for normal insurance uncertainty, such as claims being more frequent or severe than expected. | Protects against ordinary insurance risk being worse than planned. |
| Catastrophe capital | Capital for major event risk. | Protects against rare events that can create large losses. |
| Market & Credit capital | Capital for investment, reinsurer, and counterparty risks. | Protects against reinsurers not paying, investments moving against the insurer, or credit problems. |
| Diversification benefit | Reduction in capital because not all risks are expected to go badly at the same time. | Shows the benefit of spreading risk across different risk types. |

### Decision Reasons, Detailed Explanation, and Remediation

| Section | What it means | How to use it |
|---|---|---|
| Decision reasons | Short explanation of why the app chose Quote, Requires Review, or Decline. | Use this as the headline answer. |
| Detailed explanation | Longer explanation with numbers, such as requested limit versus appetite, risk score, expected loss, and capital strain. | Use this to understand the main drivers behind the decision. |
| What can make it acceptable | Suggested changes that could move a risk from Decline to Refer or Quote. | Examples include lowering the limit, adding sublimits, increasing deductible, improving controls, or adding reinsurance. |
| Rule checks | A rule-by-rule table showing status and evidence. | Use this to audit which rules passed, sent for review, or declined. |
| Model basis note | Explains that the model blends ML estimates with underwriting rules and uses proxy RBC factors. | Helps prevent over-reliance on the prototype. |

## Tab 2: Data

The Data tab shows the feed tables used by the model. Think of each feed as a spreadsheet that would eventually come from a company system or external provider. In the current prototype, these feeds are generated so the full workflow can run without production data.

### Top Metrics

| Data point | What it means | Why it matters |
|---|---|---|
| Policies | Number of policy records in the current run. | More policies give the model more examples for dashboards and training. |
| Claim rate | Percentage of policy records with at least one claim. | A simple measure of how often claims occur. |
| Mean technical premium | Average model premium across policies. | Shows the typical price level in the current portfolio. |
| Mean expected loss | Average expected claim cost across policies. | Shows the typical claims cost before expenses, profit, and capital charges. |

### Data Feed Selector

| Feed | Plain-English meaning |
|---|---|
| policies | One row per policy. This is the main training and underwriting table. |
| premiums | Written and earned premium, commission, and fee amounts for each policy. |
| exposures | The insured values, limits, deductibles, location quality, and exposure units. |
| claims | Individual claim records with paid, case reserve, incurred loss, cause, and development year. |
| reinsurance | Recoverables, ceded share, reinsurer name, rating, collateral, and default-loss estimates. |
| economic_indices | Monthly inflation, repair-cost, material-cost, and medical/wage cost indices. |
| traffic_events | Regional motor accident and bodily injury severity indices. |
| weather_events | Regional rainfall, sandstorm, heat, and wind indices by month. |
| cat_events | Major event scenarios such as flash flood, sandstorm, fire/explosion, and project clash events. |
| market_curves | Base and stressed interest-rate and credit-spread assumptions. |
| rbc_factors | Proxy factors and correlations used in capital calculations. |

### Metadata Coverage Table

| Column | What it means |
|---|---|
| table | Feed name. |
| rows | Number of rows in that feed. |
| has_required_metadata | Whether the feed contains the required traceability columns. |
| source_type | Whether the row came from the current generated data source. In production this would identify the real source category. |
| scenario_id | The scenario used to produce the data. |

Required metadata columns include record ID, valuation date, source type, source name, production-required flag, scenario ID, and seed. These make the feed auditable.

## Tab 3: Actuarial

The Actuarial tab shows transparent baseline models. These are deliberately simpler than the predictive ML layer so a model owner can explain them to auditors and regulators.

### GLM Baseline Diagnostics

| Data point | What it means |
|---|---|
| Poisson GLM frequency | A model that estimates how many claims a policy may produce. |
| Gamma GLM severity | A model that estimates how large claims may be when claims occur. |
| rows_fit | Number of policy rows used to fit the model. |
| target | The value the model was trained to predict. |
| aic | A model-fit score used for comparing actuarial models. Lower is usually better when comparing similar models. |
| deviance | A measure of how much unexplained variation remains after fitting the model. |
| basis | Plain-English description of what the model is intended to do. |

### GLM Indications

| Column | What it means |
|---|---|
| glm_claim_frequency | GLM estimate of expected claim count or claim likelihood for a policy. |
| glm_claim_severity_sar | GLM estimate of claim size in SAR. |
| glm_expected_loss_sar | Frequency multiplied by severity after deductible effect. |
| glm_technical_premium_sar | Premium implied by the GLM expected loss and pricing assumptions. |
| glm_loss_ratio | GLM expected loss divided by GLM technical premium. |

## Tab 4: Model Diagnostics

This tab explains the predictive ML layer. The current full model uses XGBoost for claim frequency and claim cost, with SHAP used to explain the current quote.

### Predictive ML Diagnostics

| Data point | What it means |
|---|---|
| rows | Number of policy rows used for training and testing. |
| claim_rate | Share of training policies with at least one claim. |
| frequency_auc | How well the frequency model separates claim and non-claim policies. 0.5 is weak; closer to 1.0 is better. |
| loss_rmse_log | Error measure for claim cost predictions on a log scale. Lower is better. |
| trained_at_utc | Timestamp when the model was trained. |
| model_type | The algorithm used, currently XGBoost for the full ML layer. |
| basis | Short description of the training basis. |

### Feature Importance

| Data point | What it means |
|---|---|
| feature | Input used by the model after preprocessing. Numeric features start with `num__`; category flags start with `cat__`. |
| importance | How much the fitted model used that feature across all trees. |

### SHAP Explanation

| Data point | What it means |
|---|---|
| feature | A transformed model input that affected the current quote. |
| contribution | Direction and size of that feature's effect on the claim-probability prediction. Positive pushes risk up; negative pushes risk down. |
| absolute_contribution | Size of the effect regardless of direction. |

## Tab 5: Reserving

The Reserving tab estimates unpaid claims. Reserving is about claims that have already happened or may have happened but are not fully paid yet.

### Reserve Summary

| Column | What it means |
|---|---|
| lob | Insurance type. |
| paid_loss_sar | Claims already paid. |
| incurred_loss_sar | Paid losses plus current case reserves. |
| case_reserve_sar | Claim handler estimate of remaining unpaid amounts. |
| chain_ladder_reserve_sar | Reserve estimate from observed claim development patterns. |
| bornhuetter_ferguson_reserve_sar | Reserve estimate blending expected loss with observed paid claims. |
| selected_reserve_sar | The reserve carried forward into capital calculations. |
| earned_premium_sar | Premium earned for the risk period. |

### Triangles and Link Ratios

| Data point | What it means |
|---|---|
| Paid triangle | Cumulative paid claims by accident year and development year. |
| Incurred triangle | Cumulative incurred claims by accident year and development year. |
| Link ratios | Selected development factors used to project claims from one development age to the next. |

## Tab 6: Capital

The Capital tab expands the MVP three-module capital view into a fuller proxy SCR view.

### Top Metrics

| Data point | What it means |
|---|---|
| Standalone capital | Sum of all module capital before diversification. |
| Diversified SCR | Capital after applying the correlation matrix. |
| Diversification benefit | Reduction from diversification because not every risk is assumed to peak at the same time. |

### Expanded SCR Modules

| Module | What it means |
|---|---|
| Premium risk | Risk that future claims from current policies are worse than priced. |
| Reserve risk | Risk that claim reserves are not enough. |
| Catastrophe risk | Risk from large events such as flood, sandstorm, fire/explosion, or project clash. |
| Reinsurance credit risk | Risk that reinsurers do not pay recoverables fully or on time. |
| Market risk | Risk from interest rates, credit spreads, and SAR/USD peg basis assumptions. |

### Capital Detail Selector

The Capital detail selector lets you inspect the source table behind each module. For example, premium risk shows premium and expected loss by LOB, while reinsurance credit risk shows recoverables and credit capital by reinsurer.

## Tab 7: Scenarios

The Scenarios tab reruns the generated data and capital engine under multiple stress cases.

| Scenario | Plain-English meaning |
|---|---|
| Base | Normal proxy assumptions. |
| High Inflation | Claim repair, spare-part, and construction material costs rise. |
| Severe Flood Year | Western and central flood losses are much higher. |
| Sandstorm Heavy Year | Sandstorm and windblown-dust events become more frequent or severe. |
| Reinsurer Downgrade/Default | Reinsurance recoverables become riskier and some default. |
| Interest Rate Shock | Fixed-income values are stressed by rate and spread movements. |
| Giga Project Accumulation | Large engineering and construction packages accumulate in one event footprint. |

Scenario columns show diversified SCR, standalone capital, diversification benefit, and each capital module. Change versus Base shows how much a stress case moves capital.

## Tab 8: Rules

The Rules tab translates the app's decision logic into plain language.

### Business Rules in Natural Language

| Column | What it means |
|---|---|
| Rule | Name of the rule. |
| Natural language | Plain-English explanation of what the rule does. |
| Where it is applied | Technical expression used by the app. This helps developers and model owners trace the rule back to code. |

Important rules include:

| Rule | Plain-English meaning |
|---|---|
| LOB appetite limit | Decline if the requested coverage limit is above the maximum allowed for that insurance type. |
| Controls plus extreme risk | Decline if controls are very weak and the total risk score is already very high. |
| Unrated reinsurance concentration | Decline if too much risk is passed to an unrated reinsurer. |
| Composite risk score | Decline if the overall risk score is outside appetite. |
| Review band | Require review if the risk is not bad enough to decline but too risky to auto-quote. |
| Capital strain review | Require review if the policy needs too much capital compared with its premium. |
| Accumulation review | Require review if one event could cause many claims together. |
| High cession review | Require review if the quote depends heavily on reinsurance. |

## Tab 9: Proxy Factors

The Proxy Factors tab shows configuration assumptions. These are not official regulatory values.

| Section | What it means |
|---|---|
| LOB factors | Base frequency, base severity, base rate, minimum premium, maximum limit, expense ratio, profit margin, and cost of capital by LOB. |
| Three-module policy correlations | The older policy-level underwriting/catastrophe/market-credit correlation matrix used on the quote screen. |
| Expanded SCR correlations | The full premium/reserve/cat/reinsurance/market correlation matrix used in the Capital tab. |
| Scenario assumptions | Multipliers and shocks used to generate each stress scenario. |
| Generated RBC factor feed | Feed-style view of proxy factors and correlation rows. |

## How to Interpret a Typical Result

If the app returns Quote:

- The request is within current appetite.
- The premium is available as an offered price.
- The risk still has expected loss and capital cost, but no hard rule blocks it.

If the app returns Requires Review:

- The request is not automatically declined.
- A human approver should check the specific review trigger.
- Common reasons include high risk score, high capital strain, high accumulation, or heavy reinsurance dependence.

If the app returns Decline:

- The request is outside current appetite as entered.
- The detailed explanation should show why.
- The remediation section suggests changes that may make the request acceptable, such as reducing the limit, increasing deductible, improving controls, adding sublimits, or changing reinsurance support.

## Important Prototype Caveat

The app is built for exploration and demonstration. It should not be used as final pricing, reserving, regulatory capital, or underwriting authority without:

- real company exposure and claims data,
- approved actuarial calibration,
- official Saudi RBC factor interpretation,
- governance approval,
- production validation, and
- legal/compliance approval.
