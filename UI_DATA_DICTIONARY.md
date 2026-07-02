# Xtract.io for Chubb Arabia UI Data Dictionary

This document explains the data points shown across both user interfaces in this repository:

1. **Streamlit risk model app** in `app.py`, titled **Chubb Arabia Portfolio Risk Model**.
2. **React underwriting workbench** in `frontend/src/App.tsx`, titled **Xtract.io for Chubb Arabia**.

The explanations are written for a non-insurance reader. The system is a prototype for Saudi Arabia property and casualty insurance. Property and casualty, or P&C, covers risks such as vehicles, buildings, construction projects, cargo, and liability claims.

## Shared Terms

| Term | Plain-English meaning |
|---|---|
| SAR | Saudi Riyal, the currency used throughout the prototype. |
| Policy | An insurance contract, quote request, or prospective insurance arrangement. |
| Application | A structured request for insurance that has entered the underwriting workflow. |
| Portfolio | A collection of policies or applications. |
| Line of business, or LOB | The type of insurance, such as Motor, Property & Fire, Engineering & Construction, Marine & Cargo, or Casualty/Liability. |
| Premium | The price charged to the customer for insurance. |
| Claim | A request for payment after a covered loss. |
| Expected loss | The model's estimate of average future claim cost. |
| Coverage limit | The maximum amount the insurer may pay for a covered loss. |
| Deductible | The amount the customer pays before insurance starts paying. |
| Exposure value | The value, size, or scale of what is being insured. |
| Reinsurance | Insurance bought by the insurer to share large losses with another insurer. |
| Ceded share | The percentage of risk passed to reinsurers. |
| Risk controls | Safety, operational, fire, security, or governance measures that reduce risk. |
| Event accumulation | The chance that one event affects many insured items at once. |
| SCR | Solvency Capital Requirement. In this prototype it is a proxy capital estimate, not an official regulatory filing. |
| RBC | Risk-Based Capital. A solvency approach where required capital depends on the risks being written. |
| Catastrophe or Cat | A major event such as flash flood, sandstorm, fire, explosion, or project clash event. |
| Appetite | The insurer's current willingness to accept a risk under defined limits and controls. |
| STP | Straight-through processing. The system can proceed without human review. |
| Requires review | The system does not decline, but a human underwriter must check and approve or change the terms. |
| Decline | The system says the request is outside appetite as entered. |
| Bind | Convert an accepted quote into an active policy. A quote is an offer; binding makes it effective. |

## Streamlit App: Chubb Arabia Portfolio Risk Model

The Streamlit app is the analytical risk model and capital sandbox. It lets a model owner test underwriting decisions, pricing components, reserving, scenario impacts, and proxy RBC capital using generated data feeds.

### Sidebar: Model Run

| Data point | What it means | Why it matters |
|---|---|---|
| Data rows | Number of generated portfolio records used to train models and populate analytics. | More rows give the models more examples, but the app may take longer to run. |
| Random seed | A number that makes the generated data repeatable. | The same seed and row count reproduce the same demonstration data. |
| Scenario | The selected assumption set, such as Base, High Inflation, Severe Flood Year, Sandstorm Heavy Year, Reinsurer Downgrade/Default, Interest Rate Shock, or Giga Project Accumulation. | Lets users see how the portfolio behaves under normal and stressed conditions. |
| Scenario caption | Text description of the selected scenario. | Explains what kind of stress is being applied. |
| Prototype notice | Reminder that data and factors are generated/proxy assumptions. | Prevents users from treating outputs as official pricing or regulatory results. |

### Streamlit Tab: Underwriting

The Underwriting tab prices one policy request and explains whether the risk should be quoted, reviewed, or declined.

#### Common Policy Inputs

| Data point | What it means | Why it matters |
|---|---|---|
| Line of business | Insurance type being requested. | Each LOB has different claim behavior, appetite limits, catastrophe exposure, and pricing assumptions. |
| Region | Saudi region or market area where the risk is located or operates. | Region affects traffic density, flood exposure, sandstorm exposure, industrial concentration, and logistics exposure. |
| Reinsurer rating | Credit quality of the reinsurer, such as AAA, AA, A, BBB, BB, or Unrated. | Weak or unrated reinsurers increase counterparty risk. |
| Exposure value | Value or size of what is insured. | Higher exposure means more value at risk. |
| Coverage limit | Maximum amount the insurer may pay. | High limits can exceed appetite even when expected loss is modest. |
| Deductible | Amount the customer pays first. | Higher deductibles reduce the insurer's small-loss burden. |
| Term | Policy length in months. | Longer policies expose the insurer to risk for more time. |
| Prior claims, 3Y | Number of claims in the past three years. | More prior claims often indicate higher future risk. |
| Risk controls | 0 to 100 score for quality of risk management. Higher is better. | Strong controls can lower expected loss and reduce review concern. |
| Reinsurance ceded | Percentage of the risk passed to a reinsurer. | Reduces retained loss but increases dependence on the reinsurer. |
| Event accumulation | 0 to 100 score for one-event concentration. | High accumulation means one event could create many claims together. |

#### Motor Inputs

| Data point | What it means | Why it matters |
|---|---|---|
| Policy type | Comprehensive or Compulsory. | Comprehensive coverage is broader and usually more claim-prone. |
| Vehicle class | Vehicle category such as private car, SUV, taxi/ride-hailing, light commercial, or heavy truck. | Vehicle use and weight affect claim frequency and severity. |
| Driver age | Age of main driver. | Very young or older drivers may have different claim patterns. |
| Vehicle age | Age of vehicle in years. | Older vehicles can have different repair and safety characteristics. |
| Fleet size | Number of vehicles insured. | More vehicles increase claim opportunity. |

#### Property & Fire Inputs

| Data point | What it means | Why it matters |
|---|---|---|
| Occupancy | Property use, such as residential, retail, warehouse, manufacturing, or petrochemical support. | Some uses are more hazardous than others. |
| Fire protection | Quality of sprinklers, alarms, hydrants, and procedures. | Better protection can reduce fire losses. |
| Construction quality | Building resilience and quality. | Better construction reduces severity from fire, flood, and wind. |
| Hazard score | Inherent hazard of the property use. | Higher hazard means more risk before controls are considered. |

#### Engineering & Construction Inputs

| Data point | What it means | Why it matters |
|---|---|---|
| Project type | Civil works, renewables, rail, industrial plant, or giga-project package. | Large or complex projects can have severe and hard-to-predict losses. |
| Duration | Project length in months. | Longer projects create more time for loss events. |
| Contractor experience | Contractor's years of experience. | More experience is assumed to improve project execution and controls. |
| Complexity score | Difficulty of the project. | Higher complexity increases uncertainty and loss potential. |

#### Marine & Cargo Inputs

| Data point | What it means | Why it matters |
|---|---|---|
| Cargo type | Goods being transported, such as general cargo, electronics, pharma/cold chain, project cargo, or hazardous cargo. | Fragile, temperature-sensitive, oversized, or hazardous cargo is riskier. |
| Transit distance | Distance cargo travels. | Longer routes create more opportunity for loss. |
| Storage days | Days cargo is stored during transit. | More storage time can increase damage, theft, or accumulation risk. |
| Cargo risk | Inherent risk score for the cargo. | Summarizes value concentration, handling difficulty, and sensitivity. |

#### Casualty/Liability Inputs

| Data point | What it means | Why it matters |
|---|---|---|
| Liability type | General liability, professional indemnity, D&O, or product liability. | Different liability covers produce different lawsuit and settlement patterns. |
| Annual revenue | Insured company's yearly revenue. | Larger companies can face larger and more frequent liability claims. |
| Limit intensity | How large the requested limit is relative to business size. | High limit intensity can indicate unusual severity potential. |
| Professional risk | Professional or management-related risk score. | Higher score means more risk from errors, negligence, or management disputes. |

#### Underwriting Outputs

| Data point | What it means | Why it matters |
|---|---|---|
| Decision badge | Quote, Requires Review, or Decline. | Main underwriting answer. |
| Offered premium | Rounded premium offered if the risk can be quoted or reviewed. | The price shown to the user. |
| Risk score | 0 to 100 risk score. Higher is riskier. | Combines expected loss, severity, controls, accumulation, capital strain, and other risk factors. |
| Expected loss | Average claim cost expected for the policy. | Core insurance cost before expenses, profit, and capital loads. |
| SCR impact | Proxy capital needed for this policy. | A profitable risk can still consume substantial capital. |
| Premium chart | Visual split of price components. | Shows whether price is driven by claims, catastrophe, capital, expenses, or margin. |
| Pricing reconciliation | Side-by-side view of predictive ML and selected pricing view. | Explains how the technical price compares with model estimates. |
| Capital chart | Underwriting, catastrophe, and market/credit capital for the policy. | Shows which risk module drives capital need. |
| Diversification benefit | Capital reduction because risks do not all peak together. | Explains why total capital is less than the sum of standalone pieces. |
| Decision reasons | Short explanation of the decision. | Useful as the headline answer for business users. |
| Detailed explanation | Numeric driver comments. | Shows why the model reached its decision. |
| What can make it acceptable | Suggested remediation actions. | Helps move a risk from decline/review toward acceptable terms. |
| Rule checks | Rule-by-rule evidence table. | Gives auditability and traceability to underwriting logic. |
| Model basis note | Description of ML/rules/proxy basis. | Reminds users that this is a prototype model. |

### Streamlit Tab: Data

The Data tab shows the generated feeds used by the model.

| Data point | What it means |
|---|---|
| Policies | Count of policy records in the current model run. |
| Claim rate | Percentage of policies with at least one claim. |
| Mean technical premium | Average model premium across the generated policies. |
| Mean expected loss | Average expected claim cost across the generated policies. |
| Data feed selector | Chooses which feed table to inspect. |
| Metadata coverage | Shows feed row counts and required traceability fields. |
| LOB count chart | Number of policies by line of business. |
| Loss ratio histogram | Distribution of observed loss ratio by LOB. |
| Selected feed table | First 250 rows of the chosen feed. |

#### Data Feeds

| Feed | Plain-English meaning |
|---|---|
| policies | One row per policy. Main underwriting and training table. |
| premiums | Written/earned premium, commissions, and fees. |
| exposures | Insured values, limits, deductibles, locations, and exposure units. |
| claims | Claim records with paid amount, reserve, incurred loss, cause, and development year. |
| reinsurance | Ceded share, recoverables, reinsurer, rating, collateral, and default-loss estimates. |
| economic_indices | Inflation, spare-part, material, medical, and wage cost indices. |
| traffic_events | Regional motor accident and bodily injury severity indicators. |
| weather_events | Rainfall, sandstorm, heat, and wind indicators. |
| cat_events | Major event scenarios such as flood, sandstorm, fire/explosion, and project clash. |
| market_curves | Base and stressed interest-rate and credit-spread assumptions. |
| rbc_factors | Proxy RBC factors and correlations used in capital calculations. |

### Streamlit Tab: Actuarial

| Data point | What it means |
|---|---|
| GLM baseline diagnostics | Fit statistics for transparent actuarial models. |
| Poisson GLM frequency | Baseline model for claim count or claim likelihood. |
| Gamma GLM severity | Baseline model for claim size when a claim happens. |
| AIC | Model comparison statistic; lower is usually better for similar models. |
| Deviance | Remaining unexplained variation after fitting. |
| Indication summary | Average GLM claim frequency, severity, expected loss, and premium by LOB. |
| GLM expected loss scatter | Visual comparison of GLM expected loss and GLM technical premium. |
| GLM indications table | Policy-level actuarial output used as a baseline check. |

### Streamlit Tab: Model Diagnostics

| Data point | What it means |
|---|---|
| Predictive ML diagnostics | Training and test metrics for frequency/severity models. |
| rows | Number of records used by the model. |
| claim_rate | Share of model records with a claim. |
| frequency_auc | Ability of the claim-frequency model to separate claim and non-claim policies. |
| loss_rmse_log | Severity model error on a log scale. Lower is better. |
| model_type | Algorithm used, currently XGBoost in the full model layer. |
| Frequency model importance | Inputs the frequency model used most. |
| Severity model importance | Inputs the severity model used most. |
| SHAP explanation | Feature-level explanation for the current quote. |
| SHAP contribution | Direction and size of a feature's effect. Positive raises predicted risk; negative lowers it. |

### Streamlit Tab: Reserving

| Data point | What it means |
|---|---|
| Reserve summary | LOB-level estimate of unpaid claims. |
| paid_loss_sar | Claims already paid. |
| incurred_loss_sar | Paid loss plus current case reserves. |
| case_reserve_sar | Claim handler estimate of unpaid amounts. |
| chain_ladder_reserve_sar | Reserve from observed development patterns. |
| bornhuetter_ferguson_reserve_sar | Reserve blending expected loss with observed paid claims. |
| selected_reserve_sar | Reserve carried forward into capital calculations. |
| Paid triangle | Cumulative paid claims by accident year and development year. |
| Incurred triangle | Cumulative incurred claims by accident year and development year. |
| Link ratios | Development factors used to project claims to maturity. |

### Streamlit Tab: Capital

| Data point | What it means |
|---|---|
| Standalone capital | Sum of module capital before diversification. |
| Diversified SCR | Capital after applying the correlation matrix. |
| Diversification benefit | Reduction because not all risks are assumed to peak together. |
| Module capital chart | Premium, reserve, catastrophe, reinsurance credit, and market capital by module. |
| Capital detail selector | Chooses the source detail table for a module. |
| Expanded module correlations | Correlation matrix for the full capital model. |
| Legacy three-module policy sample | Older policy-level underwriting/catastrophe/market-credit view retained for comparison. |

### Streamlit Tab: Scenarios

| Data point | What it means |
|---|---|
| Scenario comparison chart | Diversified SCR across stress scenarios. |
| standalone_sum_sar | Total standalone capital in a scenario. |
| diversified_scr_sar | Diversified capital in a scenario. |
| diversification_benefit_sar | Capital reduction from diversification. |
| premium_risk_sar | Capital from future claim volatility. |
| reserve_risk_sar | Capital from reserve uncertainty. |
| catastrophe_risk_sar | Capital from major events. |
| reinsurance_credit_risk_sar | Capital from reinsurer non-payment or downgrade. |
| market_risk_sar | Capital from interest-rate, spread, and peg-basis stress. |
| change_vs_base_sar / pct | Movement versus the Base scenario. |

### Streamlit Tab: Rules

| Data point | What it means |
|---|---|
| Business rules in natural language | Plain-English version of the underwriting rules. |
| Where it is applied | Technical expression or condition used in code. |
| Decision thresholds | Numeric cutoffs for STP, review, and decline. |
| LOB appetite limits | Maximum limit, minimum premium, expense ratio, margin, and cost of capital by LOB. |

### Streamlit Tab: Proxy Factors

| Data point | What it means |
|---|---|
| LOB factors | Pricing and capital assumptions by line of business. |
| Three-module policy correlations | Underwriting/catastrophe/market-credit correlation matrix. |
| Expanded SCR correlations | Full premium/reserve/cat/reinsurance/market correlation matrix. |
| Scenario assumptions | Multipliers and shocks used in each scenario. |
| Generated RBC factor feed | Feed-style view of proxy factors and correlations. |

## React App: Xtract.io for Chubb Arabia

The React app is the operational underwriting workbench. It simulates how a quote request enters the insurer, gets extracted from documents, becomes a structured application, is enriched, triaged, reviewed, quoted, and bound.

### Common React Workbench Layout

| UI element | What it means |
|---|---|
| Sidebar navigation | Switches between Unstructured Intake, Intake, Triage, Review Queue, Quote & Bind, and Config. |
| Collapsed sidebar | Icon-only navigation to preserve screen space. Expanding it shows the Xtract logo and role selector. |
| Role selector | Demo role: Agent, Underwriter, or Manager. It affects actor labels in audit events but is not authentication. |
| Case strip | Horizontal list of recent applications or unstructured records. |
| Status pill | Current workflow state, such as Submitted, STP Quoted, Requires Review, Quoted, Bound, Failed, Rejected, or Application Created. |
| Refresh button | Reloads current queues and case state. |
| Page title | Shows the selected uploaded record or selected applicant/case. |

### React Screen: Unstructured Intake

This screen comes before formal application intake. It is used for uploaded emails, PDFs, CSV files, or spreadsheets that need extraction and human review.

| Data point | What it means | Why it matters |
|---|---|---|
| Upload | Accepts `.eml`, `.pdf`, `.csv`, `.xlsx`, and `.xls` files. | Lets applications enter from real-world documents rather than only forms. |
| Extract | Runs the extraction service. | Converts raw documents into structured applicant and policy fields. |
| Approve | Human reviewer accepts the extracted values. | Approval creates a structured application. |
| Reject | Human reviewer rejects the extraction. | Prevents poor extraction from entering the underwriting workflow. |
| Record chip | Uploaded file or spreadsheet row awaiting review. | Keeps the pre-intake queue visible without consuming the main screen. |
| Batch row | Row number for CSV/Excel-derived records. | A single spreadsheet can create multiple intake records. |
| Raw Record | Original file preview and extracted raw text. | Lets the reviewer compare the source document with extracted fields. |
| PDF iframe | In-browser PDF preview for uploaded PDFs. | Keeps the source visible during HITL review. |
| Raw text preview | Text extracted from the original source. | Useful when the original file is not visually readable. |
| Extracted Values | Editable structured fields produced by extraction. | The reviewer can correct values before approval. |
| Confidence badge | `high` or `low` confidence for each extracted attribute. | Tells the reviewer which fields need more attention. |
| Confidence tooltip | Evidence and rationale behind a confidence score. | Explains why the extractor trusted or distrusted a value. |
| Missing field chips | Required fields that were not found. | Focuses reviewer attention on gaps. |
| Warning chips | Issues such as defaulted values or unusual limits. | Shows extraction or business-quality concerns. |
| Application created note | Confirmation that approval created an application. | Links HITL completion to the underwriting workflow. |

#### Extracted Fields in HITL Review

| Field | Meaning |
|---|---|
| Applicant type | Company or individual. |
| Applicant name | Legal or trading name of the insured. |
| National ID / CR | Saudi national ID or commercial registration identifier. |
| Email | Contact email for applicant or agent. |
| Phone | Contact phone number. |
| LOB | Insurance line being requested. |
| Region | Location or operating region. |
| Reinsurer rating | Credit quality of supporting reinsurer. |
| Term months | Policy length. |
| Exposure value | Scale or value insured. |
| Coverage limit | Maximum claim payment requested. |
| Deductible | Customer's first-loss amount. |
| Prior claims | Recent claim count. |
| Risk controls | Control quality score. |
| Reinsurance ceded | Share of risk passed to reinsurers. |
| Event accumulation | One-event concentration score. |
| LOB-specific fields | Motor, property, engineering, marine, or liability fields described in the Streamlit section above. |

### React Screen: Intake

This screen manually creates a structured application without going through unstructured document extraction.

| Data point | What it means |
|---|---|
| Channel | How the request entered: manual or API. |
| Applicant type | Company or individual. |
| Applicant name | Name of insured applicant. |
| National ID / CR | Official identifier. |
| Email | Contact email. |
| Phone | Contact phone. |
| LOB | Requested insurance type. |
| Region | Risk location or operating region. |
| Reinsurer rating | Credit rating of reinsurer. |
| Term months | Policy term. |
| Exposure value | Value or scale insured. |
| Coverage limit | Maximum insurance amount requested. |
| Deductible | First amount paid by customer. |
| Prior claims | Recent claim count. |
| Risk controls | Control quality score. |
| Reinsurance ceded | Risk share passed to reinsurer. |
| Event accumulation | One-event accumulation score. |
| Submit | Creates the structured application and moves it into the case list. |

### React Screen: Triage

The Triage screen runs generated enrichment and underwriting/rating logic.

| Data point | What it means | Why it matters |
|---|---|---|
| Enrich | Calls generated provider services. | Simulates third-party verification and supplemental data. |
| Underwrite | Runs rules, risk scoring, rating, and triage. | Produces STP, requires-review, or decline decision. |
| Enrichment Timeline | Provider responses and flags. | Shows what external checks found. |
| Provider name | Service such as identity/financial, reinsurance security, motor MVR/CLUE, property geospatial, engineering project intelligence, marine logistics intelligence, or liability/public records. | Indicates where the supplemental evidence came from. |
| Provider confidence | Approximate confidence in provider result. | Low confidence may require manual attention. |
| Flags | Low, medium, or high severity issues from enrichment. | Flags can influence review or decline. |
| Triage & Rating | Decision and price/risk summary. | Shows the outcome of rules and rating. |
| Decision bucket | STP, Requires Review, or Declined. | Determines next workflow step. |
| Decision reasons | Human-readable reason list. | Explains the outcome. |
| Adjusted premium | Offered technical premium after adjustments. | Price output after discounts/surcharges. |
| Expected loss | Average expected claim cost. | Underlying insurance cost. |
| Risk score | Overall risk score. | Main numeric risk measure. |
| SCR | Proxy capital required. | Capital impact of the case. |
| Adjustments | Discounts or surcharges. | Shows how controls, prior claims, and other factors moved the premium. |

### React Screen: Review Queue

This screen is for cases that require human underwriter review.

| Data point | What it means |
|---|---|
| Review Queue list | Cases currently in requires-review status. |
| Applicant name | Insured name in the queue row. |
| LOB | Insurance type in the queue row. |
| Premium | Current adjusted premium estimate. |
| Assignee | Underwriter assigned to the case. |
| Schedule adjustment | Manual percentage premium adjustment. Positive increases price; negative decreases it. |
| Notes | Underwriter rationale or decision comments. |
| Exclusion | Coverage wording excluded from the offer. |
| Assign | Assigns the case to an underwriter. |
| Approve | Approves a reviewed case so it can be quoted. |
| Decline | Declines the case after human review. |

### React Screen: Quote & Bind

This screen turns approved cases into quote documents and then into bound policies.

| Data point | What it means | Why it matters |
|---|---|---|
| Status | Current case status. | Shows whether the case is ready for quote or already bound. |
| Premium | Latest offered premium or rating premium. | The price being offered. |
| Risk score | Latest risk score. | Risk context for the quote. |
| SCR impact | Proxy capital impact. | Capital context for the quote. |
| Generate Quote | Creates a quote record and PDF. | Packages price, terms, and expiry. |
| PDF | Link to generated quote PDF. | Formal quote document for review/download. |
| Bind | Converts the accepted quote into an active policy. | Binding means the quote terms have been accepted and coverage is made effective in the workflow. |
| Quote number | Identifier for the quote. |
| Expires | Quote expiry date. |
| Deductible | Deductible in the quote terms. |
| Policy | Bound policy number if the quote has been bound. |
| Audit Trail | Event history for the application. | Shows who or what performed each workflow action. |
| Event type | Action name such as application.created, underwriting.decision, rating.created, quote.generated, or policy.bound. |
| Actor | User/service that performed the action. |
| Event timestamp | When the action occurred. |

### React Screen: Config

| Data point | What it means |
|---|---|
| LOB Appetite | Table of underwriting appetite by LOB. |
| MaxLimit | Maximum coverage limit currently allowed for the LOB. |
| MinPremium | Minimum premium for the LOB. |
| BaseRate | Base pricing rate for the LOB. |
| Decision Thresholds | Numeric limits for STP, review, and decline logic. |
| Threshold | Name of decision control. |
| Value | Current threshold value. |

## How the Two Apps Fit Together

| Streamlit app | React workbench |
|---|---|
| Analytical sandbox for pricing, ML, reserving, capital, scenarios, and rules. | Operational workflow simulator for intake, HITL extraction, enrichment, triage, review, quote, and bind. |
| Lets a model owner inspect data feeds, diagnostics, SHAP, reserve triangles, and capital modules. | Lets an underwriter or agent process individual applications through a realistic workflow. |
| Good for model development and governance. | Good for product, process, and underwriting-operations demonstrations. |
| Uses generated portfolio data to train and explain models. | Uses generated provider evidence plus structured application data to run decisions. |

## Prototype Caveat

Both apps are prototypes. They use generated data, generated provider evidence, company-configurable rules, and proxy capital factors. They are not final pricing authority, legal policy wording, official Saudi RBC calculations, or production underwriting controls. Production use would require real data, actuarial calibration, legal wording, authority controls, cybersecurity, audit governance, and regulator-approved assumptions.
