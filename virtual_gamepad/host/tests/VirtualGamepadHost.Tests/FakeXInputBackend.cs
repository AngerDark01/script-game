using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Tests;

internal sealed class FakeXInputBackend : IXInputBackend
{
    public bool IsConnected { get; private set; }
    public List<GamepadState> Reports { get; } = new();

    public void Start() => IsConnected = true;

    public void Submit(GamepadState state)
    {
        if (!IsConnected)
        {
            throw new InvalidOperationException("Backend is not started.");
        }

        Reports.Add(state);
    }

    public void Stop() => IsConnected = false;

    public void Dispose() => Stop();
}
