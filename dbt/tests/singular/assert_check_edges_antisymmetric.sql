{{ config(meta={'category': 'mart_quality', 'table_name': 'pokemon_check_edges'}) }}
-- pokemon_check_edges (docs/plan-synergy-checks-graph.md, G5) is built so
-- that B -> A is A -> B seen from the other side: the same matches (the
-- mirror filter is symmetric), the complementary record, and the
-- complementary log5 expectation. So every row must have its reverse, with
-- z(A->B) = -z(B->A), the same match count and the same q value. A row
-- returned here is a pair where that broke.
select
  edge.regulation_scope,
  edge.pokemon_key,
  edge.opponent_pokemon_key,
  edge.z_score,
  reverse.z_score as reverse_z_score
from {{ ref('pokemon_check_edges') }} edge
left join {{ ref('pokemon_check_edges') }} reverse
  on reverse.regulation_scope = edge.regulation_scope
  and reverse.pokemon_key = edge.opponent_pokemon_key
  and reverse.opponent_pokemon_key = edge.pokemon_key
where reverse.pokemon_key is null
  or abs(edge.z_score + reverse.z_score) > 0.001
  or edge.matches_played <> reverse.matches_played
  or edge.q_value <> reverse.q_value
