## Loss

The loss of teacher $i$ is an abstract scalar-valued function of that teacher's schedule $S_i$, with teacher $i$'s preference parameter $\gamma_i$ built into the loss itself:

$$
L_i : (S_i; \, \gamma_i) \mapsto \mathbb{R}
$$

Heterogeneous preferences live inside $L_i$: two teachers with the same schedule can incur different losses. What the loss decomposes into (dimensions, functional forms) is deliberately left open.

## Objective

$$
\begin{aligned}
\min_{x}\quad
J(x) :=
&\; \alpha \cdot \operatorname*{mean}_{i}\, L_i
&& \text{(efficiency)} \\
+&\; \beta \cdot \operatorname{CVaR}_{q}\!\big(L\big)
\quad\text{or}\quad
\beta \cdot \Big( \max_i L_i - \min_i L_i \Big)
&& \text{(fairness, overall)} \\
+&\; \sum_g \beta_g \cdot \operatorname{CVaR}_{q}\!\big(L_g\big)
+ \beta' \cdot \Big( \max_g \bar{L}_g - \min_g \bar{L}_g \Big)
&& \text{(fairness, group)} \\
+&\; \eta \cdot \sum_i \mathrm{slack}_i
&& \text{(soft violations)} \\
+&\; \delta \cdot \mathbb{E}_{\xi}\big[\,\Delta(\xi)\,\big]
&& \text{(robustness)} \\
+&\; \theta \cdot \mathrm{churn}(x, x_{\mathrm{prev}})
&& \text{(stability)}
\end{aligned}
$$

with

$$
\Delta(\xi) = J\big(\hat{S}(\xi)\big) - J_{0},
\qquad
\mathrm{churn}(x, x_{\mathrm{prev}}) = \big\| x - x_{\mathrm{prev}} \big\|_{1}
$$

- **Fairness** — CVaR over the per-teacher losses: absolute, outlier-aware, no variance double-counting; the max−min range is the linear cheap alternative.
- **Group fairness** — teachers are partitioned into groups $g$ (e.g. by department or load band); $\operatorname{CVaR}_q(L_g)$ controls the tail *within* each group, and the spread of group means $\bar{L}_g$ controls fairness *between* groups. Keeping the two as separate terms is the correct repair of v1's $\sum_g b_g\,\mathrm{var}(L_g) + c\,\mathrm{var}(L)$, which double-counted by the law of total variance.
- **Slack** — soft constraints enter as $g_i(x) \le \mathrm{slack}_i$, $\mathrm{slack}_i \ge 0$, charged linearly at $\eta$; hard constraints never get slack.
- **Robustness** — $\xi$ perturbs the input data (room migration, teacher absence); $\hat{S}(\xi)$ is the *minimally altered* feasible timetable after the shock (local repairs: merge classes, reassign a teacher), and $\Delta(\xi)$ is its new loss relative to the nominal optimum $J_0$.
- **Churn** — $L_1$ distance to last year's assignment; changes must earn their disruption.

## Feasible set

$$
\begin{aligned}
x \in \Phi(x): \quad
& \textstyle\sum_{d,\pi,r} x(c,d,\pi,r) = h(k)
&& \forall c
&& \text{(contact hours)} \\
& \text{clash-free in } c,\ s,\ t,\ r
&&
&& \text{(no double booking)} \\
& E(c) \le \mathrm{cap}(r),\ \ \mathrm{type}(r) \text{ compatible}
&& \forall c,r
&& \text{(room fit)} \\
& y(t,c) \Rightarrow q(t,c) \wedge \mathrm{avail}(t,d,\pi)
&& \forall t,c,d,\pi
&& \text{(teacher eligibility)} \\
& Z(\mathrm{IB}) = \mathrm{XMT}, \quad Z(\mathrm{AP}) = \mathrm{ZXB}
&&
&& \text{(building policy)} \\
& \tau(r_{\mathrm{prev}}, r_{\mathrm{next}}) \le \mathrm{gap}
&&
&& \text{(reachability)}
\end{aligned}
$$

Reachability is imposed along every student sequence $s$ and every teacher sequence $t$: consecutive rooms must be within travel time $\tau$ inside the gap.

## Solution report

Report the Pareto front over (efficiency, fairness, robustness) by sweeping $\varepsilon$ in

$$
\min_{x \in \Phi(x)}\ \operatorname*{mean}_{i}\, L_i
\quad \text{s.t.} \quad
\operatorname{CVaR}_{q}\!\big(L\big) \le \varepsilon
$$

not a single hand-tuned argmin — the sweep doubles as the required sensitivity analysis.