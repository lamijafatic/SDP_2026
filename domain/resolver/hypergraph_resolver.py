import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from domain.resolver.base_resolver import BaseResolver
from domain.exceptions.resolution_error import ResolutionError
from model_math_trans import build_hypergraph, solve_phased


class HypergraphResolver(BaseResolver):
    """
    Two-phase dependency resolver based on the HyperRes formalism.

    Phase A: SAT over role classes (skeleton resolution).
    Phase B: greedy newest-first version selection with constraint validation.
    Backtracks by blocking failed role classes and replanning via Phase A.
    """

    def __init__(self, graph):
        super().__init__(graph)
        self.repo = getattr(graph, "repo", None)

    def solve(self) -> dict:
        self.validate_graph()

        H = build_hypergraph(self.graph, self.repo)
        required_names = set(self.graph.dependencies.keys())

        solution = solve_phased(H, self.graph, required_names)

        if solution is None:
            raise ResolutionError(
                "No solution found via hypergraph resolution.\n"
                "The combined constraints are unsatisfiable, or all role class "
                "combinations have been exhausted."
            )

        return solution
