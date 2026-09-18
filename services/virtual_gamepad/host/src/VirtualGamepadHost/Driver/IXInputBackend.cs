using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Driver;

public interface IXInputBackend : IDisposable
{
    bool IsConnected { get; }

    int ControllerCount { get; }

    bool IsControllerConnected(int controller);

    void Start();

    void Submit(int controller, GamepadState state);

    void Stop();
}
