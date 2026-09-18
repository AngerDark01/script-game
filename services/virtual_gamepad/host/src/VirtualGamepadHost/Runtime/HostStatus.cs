using VirtualGamepadHost.Driver;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Runtime;

public sealed record HostStatus(
    RunState RunState,
    bool DriverInstalled,
    bool DeviceConnected,
    string Message,
    IReadOnlyList<ControllerStatus>? Controllers = null);

public sealed record ControllerStatus(
    int Controller,
    RunState RunState,
    bool DeviceConnected,
    VirtualGamepadHost.Model.GamepadState State,
    string InputOwner = "local");
