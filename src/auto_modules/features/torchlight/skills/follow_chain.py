"""Torchlight skill/follow event-chain facade.

The execution algorithm lives in the generic action-sequence runtime. This
module owns the Torchlight-facing name so feature code does not depend on a
legacy core module path.
"""

from auto_modules.core.events.automation.action_sequence import (
    ActionSequenceDefinition,
    ActionSequenceHandler,
    BUTTONS,
    button_mask,
    inputs_mask,
)


class TorchlightSkillChainDefinition(ActionSequenceDefinition):
    """Configured action sequence used by Torchlight follow and skill flows."""


SkillChainDefinition = TorchlightSkillChainDefinition
FollowChainDefinition = TorchlightSkillChainDefinition
FollowChainHandler = ActionSequenceHandler

__all__ = [
    "TorchlightSkillChainDefinition",
    "SkillChainDefinition",
    "FollowChainDefinition",
    "FollowChainHandler",
    "BUTTONS",
    "button_mask",
    "inputs_mask",
]
