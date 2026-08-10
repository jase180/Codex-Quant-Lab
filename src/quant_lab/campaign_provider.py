"""Campaign proposal provider boundary."""

from __future__ import annotations

from .campaign import CampaignConfig, CampaignState
from .campaign_proposal import CampaignProposal, deterministic_campaign_proposal


def campaign_provider_proposal(config: CampaignConfig, state: CampaignState) -> CampaignProposal:
    """Return one campaign proposal from the configured provider.

    The controller owns validation, execution, budgets, and persistence. A
    provider only returns a strict `CampaignProposal`, which keeps future model
    adapters from gaining control over the campaign loop.
    """

    if config.provider == "deterministic":
        return deterministic_campaign_proposal(config, state)
    if config.provider in {"ollama", "codex"}:
        raise NotImplementedError(
            f"campaign provider {config.provider!r} is not implemented yet; use provider 'deterministic'"
        )
    raise ValueError(f"unsupported campaign provider: {config.provider}")
