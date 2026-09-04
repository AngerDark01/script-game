using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Driver;

public static class ControllerBackendExtensions
{
    public static void Submit(this IXInputBackend backend, GamepadState state)
        => backend.Submit(1, state);
}
