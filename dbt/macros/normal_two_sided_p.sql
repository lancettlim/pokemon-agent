{#
  Two-sided p-value for a standard-normal z score, P(|Z| >= |z|).

  DuckDB has no erf/erfc, so this is Abramowitz and Stegun's 7.1.26
  rational approximation of erfc (absolute error under 1.5e-7), applied at
  x = |z| / sqrt(2): p = erfc(x). Ample for a Benjamini-Hochberg cut at
  q <= 0.10 (pokemon_check_edges, docs/plan-synergy-checks-graph.md G2).
#}
{% macro normal_two_sided_p(z) %}
(
  (
    0.254829592 * (1 / (1 + 0.3275911 * abs({{ z }}) / sqrt(2)))
    - 0.284496736 * power(1 / (1 + 0.3275911 * abs({{ z }}) / sqrt(2)), 2)
    + 1.421413741 * power(1 / (1 + 0.3275911 * abs({{ z }}) / sqrt(2)), 3)
    - 1.453152027 * power(1 / (1 + 0.3275911 * abs({{ z }}) / sqrt(2)), 4)
    + 1.061405429 * power(1 / (1 + 0.3275911 * abs({{ z }}) / sqrt(2)), 5)
  ) * exp(-((abs({{ z }}) / sqrt(2)) * (abs({{ z }}) / sqrt(2))))
)
{% endmacro %}
