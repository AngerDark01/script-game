using VirtualGamepadHost.Input;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Runtime;

public sealed record ControllerSlot(
    int Number,
    StateStore Store,
    SafetyController Safety,
    MappingEngine Mapping);
