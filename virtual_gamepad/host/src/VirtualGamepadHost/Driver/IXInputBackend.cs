using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Driver;

public interface IXInputBackend : IDisposable
{
    bool IsConnected { get; }

    void Start();

    void Submit(GamepadState state);

    void Stop();
}
