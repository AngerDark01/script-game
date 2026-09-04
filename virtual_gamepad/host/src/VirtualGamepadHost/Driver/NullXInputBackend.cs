using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Driver;

/// <summary>
/// Keeps the protocol and UI usable when ViGEmBus is not installed.
/// It never claims a connected device and intentionally discards reports.
/// </summary>
public sealed class NullXInputBackend : IXInputBackend
{
    public bool IsConnected => false;

    public int ControllerCount => 2;

    public void Start() { }

    public void Submit(int controller, GamepadState state) { }

    public void Stop() { }

    public void Dispose() { }
}
