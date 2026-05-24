"""Response Consolidator for the AI ecosystem.

Merges structured outputs from multiple agent executions into a single
unified response. Handles conflict resolution, confidence weighting,
and schema normalization.
"""

from typing import Any


class ResponseConsolidator:
    """Consolidates multi-agent structured outputs into a unified response.

    When a workflow executes multiple agents, each produces its own output
    dict. The consolidator merges them, resolving conflicts by confidence
    weighting and preserving provenance (which agent produced which part).
    """

    def consolidate(
        self,
        agent_outputs: list[dict[str, Any]],
        agent_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Merge multiple agent outputs into a unified response.

        Args:
            agent_outputs: List of output dicts from agent executions.
            agent_ids: Optional list of agent identifiers for provenance.

        Returns:
            Consolidated response dict with:
                - conclusion: Merged conclusion text
                - confidence: Weighted average confidence
                - agent_contributions: Per-agent breakdown
                - conflicts: List of detected conflicts (if any)
        """
        if not agent_outputs:
            return {
                "conclusion": "No agent outputs to consolidate.",
                "confidence": 0.0,
                "agent_contributions": [],
                "conflicts": [],
            }

        ids = agent_ids or [f"agent_{i}" for i in range(len(agent_outputs))]

        contributions = []
        conclusions: list[str] = []
        confidences: list[float] = []
        conflicts: list[dict[str, Any]] = []

        for output, agent_id in zip(agent_outputs, ids):
            conclusion = output.get("conclusion", "")
            confidence = output.get("confidence", 0.5)

            contributions.append(
                {
                    "agent_id": agent_id,
                    "conclusion": conclusion,
                    "confidence": confidence,
                    "raw_output": output,
                }
            )
            conclusions.append(conclusion)
            confidences.append(confidence)

        # Weighted average confidence
        total_confidence = sum(confidences)
        avg_confidence = total_confidence / len(confidences) if confidences else 0.0

        # Detect conflicts: if conclusions differ significantly
        conflicts = self._detect_conflicts(contributions)

        # Build merged conclusion
        merged_conclusion = self._merge_conclusions(contributions)

        return {
            "conclusion": merged_conclusion,
            "confidence": round(avg_confidence, 3),
            "agent_contributions": contributions,
            "conflicts": conflicts,
        }

    def _detect_conflicts(
        self, contributions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect conflicting outputs between agents.

        A conflict is flagged when two agents have high confidence (>0.7)
        but produce different conclusions.

        Args:
            contributions: List of per-agent contribution dicts.

        Returns:
            List of conflict descriptions.
        """
        conflicts: list[dict[str, Any]] = []

        high_conf = [
            c for c in contributions if c["confidence"] > 0.7
        ]

        for i in range(len(high_conf)):
            for j in range(i + 1, len(high_conf)):
                a = high_conf[i]
                b = high_conf[j]
                if a["conclusion"] != b["conclusion"]:
                    conflicts.append(
                        {
                            "agents": [a["agent_id"], b["agent_id"]],
                            "type": "conclusion_mismatch",
                            "detail": "High-confidence agents produced different conclusions",
                        }
                    )

        return conflicts

    def _merge_conclusions(
        self, contributions: list[dict[str, Any]]
    ) -> str:
        """Merge multiple conclusions into a single text.

        For a single agent, returns its conclusion directly.
        For multiple agents, produces a summary that attributes each part.

        Args:
            contributions: List of per-agent contribution dicts.

        Returns:
            Merged conclusion string.
        """
        if len(contributions) == 1:
            return contributions[0]["conclusion"]

        parts: list[str] = []
        for c in contributions:
            parts.append(f"[{c['agent_id']}]: {c['conclusion']}")

        return " | ".join(parts)
