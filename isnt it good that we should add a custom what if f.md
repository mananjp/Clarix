<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# isnt it good that we should add a custom what if feature like let the user decide the scenario and the AI will make the judgement with all the data we need

Yes — but only if you design it as a **controlled custom what-if system**, not as an open-ended “ask AI any legal question” box. Scenario analysis is valuable because it lets teams test decisions in a simulated environment before applying them to real operations, while business rules engines add the auditability and repeatability compliance teams need.[^1][^2]

## Why this is a good idea

A custom what-if feature would make your product much more useful because real compliance teams rarely face only preset scenarios; they want to test specific business moves like changing fund classification, omitting a metric temporarily, using estimated values, or collecting employee ESG data in a different way. AI-supported scenario planning is specifically useful for evaluating uncertainty and forecasting risk, but in compliance products it works best when paired with explicit decision rules rather than freeform generation.[^3][^4][^5]

This also strengthens your uniqueness. Plenty of tools support scenario planning in general, but a compliance workflow engine that turns user-defined operational changes into obligation triggers, legal risk signals, and remediation steps is much rarer.[^6][^7]

## How to build it safely

The right architecture is:

1. User defines a scenario in structured form.
2. System translates it into normalized variables.
3. Rules engine checks which obligations are triggered.
4. AI explains consequences, ambiguity, and remediation in plain language.
5. Reviewer sees confidence, evidence, and disclaimer before accepting it.

That split matters because rules engines are good for consistent, auditable decision logic, while AI is better for interpreting messy facts and explaining outcomes.[^4][^2][^8]

## Best product design

Do **not** use a single free-text box as the primary input. Instead, use a hybrid input model:

- Scenario type: disclosure omission, threshold breach, fund reclassification, data collection change, estimation methodology change, delayed filing, control failure.
- Structured fields: framework, entity, metric, current value, proposed value, jurisdiction, reporting period.
- Optional free-text context: “We want to estimate Scope 3 using vendor averages for one quarter.”

Then let AI convert that into a normalized scenario object and show the parsed interpretation back to the user before running it. That gives flexibility without losing control. Business-rules platforms are valuable precisely because they turn policy into explicit real-time decisions instead of opaque outputs.[^9][^8]

## What the output should look like

A good custom what-if result should return:

- Triggered obligations.
- Articles or rule references involved.
- Risk level and rationale.
- Possible legal or regulatory consequences.
- Remediation options.
- Confidence level.
- Missing information needed for a firmer judgment.

For example:


| Output block | Example |
| :-- | :-- |
| Scenario | “Switch fund from Article 8 to Article 6 mid-cycle” |
| Triggered rules | SFDR classification disclosure updates, marketing material review |
| Consequence | Higher misstatement and investor-communication risk |
| Remediation | Update pre-contractual disclosures, review website language, notify reviewer/legal |
| Confidence | Medium, pending jurisdiction and filing timeline |

That makes the feature actionable instead of just interesting.[^5][^6]

## Main risk

The biggest risk is letting the AI make legal judgments without constraint. Legal-risk AI is useful for analysis and scenario generation, but if it is not tied to a rule layer and evidence model, it becomes hard to trust and hard to defend.  So the feature should always frame outputs as “AI-assisted compliance guidance” and separate:[^7][^6]

- deterministic triggered rules,
- inferred consequences,
- and uncertain legal interpretation.[^2]


## Recommended version to ship

Ship this in two modes:

- **Guided custom what-if**: form-based with optional natural language context.
- **Advanced analyst mode**: user writes a scenario in plain language, AI converts it to structured inputs, user confirms, then engine runs.

That gives flexibility without turning the feature into a hallucination trap. It also matches how scenario planning tools create safe simulation environments and how rules engines support auditable compliance decisions.[^1][^2]

So yes — adding a custom what-if feature is a very good move, and it likely becomes one of your strongest differentiators if you keep AI as the interpreter and explainer, not the sole decision-maker.[^8][^7]

A strong product label for it would be: **Custom Legal Impact Simulator**.
<span style="display:none">[^10][^11][^12][^13][^14][^15]</span>

<div align="center">⁂</div>

[^1]: https://www.epicflow.com/features/what-if/

[^2]: https://camunda.com/blog/2024/07/the-business-process-rules-engine/

[^3]: https://www.techclass.com/resources/learning-and-development-articles/role-of-ai-in-scenario-planning-and-risk-forecasting

[^4]: https://www.hyperbots.com/glossary/business-rules-engine

[^5]: https://triskellsoftware.com/blog/what-is-scenario-analysis/

[^6]: https://complinity.com/blog/compliance/legal-risk-management-artificial-intelligence-ai/

[^7]: https://www.f6s.com/software/category/legal-risk-scenario-generation

[^8]: https://inrule.com/what-is-a-business-rules-engine/

[^9]: https://www.crif.in/news-and-events/news/what-is-business-rule-engine-for-businesses-why-should-they-adopt-it-blog/

[^10]: https://www.linkedin.com/top-content/business-strategy/scenario-planning-methods/scenario-planning-for-regulatory-changes/

[^11]: https://avkalan.ai/how-ai-agents-can-transform-legal-risk-management-in-businesses/

[^12]: https://inteca.com/business-rules-engine/

[^13]: https://www.youtube.com/watch?v=L0eZsd97Z3U

[^14]: https://secureaillc.com/ai-consulting.html

[^15]: https://www.linkedin.com/pulse/most-common-questions-business-rules-engine-łukasz-niedośpiał-gdemc

