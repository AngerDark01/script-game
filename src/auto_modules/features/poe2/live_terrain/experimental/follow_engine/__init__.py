"""Process-safe building blocks for the PoE2 follow engine migration.

The package deliberately contains no Qt, game-memory, or controller side
effects.  Those integrations are added later through explicit adapters.
"""

from .replay import OfflineReplayRunner, ReplayEvent, ReplayManifest, load_replay_manifest, load_replay_scenarios
from .engine import FollowEnginePort, FollowEngineStart
from .process_supervisor import ProcessSupervisor, SupervisorState, SupervisorStatus

__all__ = [
    "FollowEnginePort",
    "FollowEngineStart",
    "OfflineReplayRunner",
    "ProcessSupervisor",
    "ReplayEvent",
    "ReplayManifest",
    "load_replay_manifest",
    "load_replay_scenarios",
    "SupervisorState",
    "SupervisorStatus",
]
