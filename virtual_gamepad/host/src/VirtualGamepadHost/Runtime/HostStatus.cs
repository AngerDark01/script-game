using VirtualGamepadHost.Driver;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Runtime;

public sealed record HostStatus(
    RunState RunState,
    bool DriverInstalled,
    bool DeviceConnected,
    string Message);
