using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Tests;

internal sealed class FakeXInputBackend : IXInputBackend
{
    public FakeXInputBackend(int controllerCount = 1)
    {
        if (controllerCount < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(controllerCount));
        }

        ControllerCount = controllerCount;
    }

    public bool IsConnected { get; private set; }
    public int ControllerCount { get; }
    public List<GamepadState> Reports { get; } = new();
    public Dictionary<int, List<GamepadState>> ReportsByController { get; } = new();

    public void Start() => IsConnected = true;

    public void Submit(int controller, GamepadState state)
    {
        if (!IsConnected)
        {
            throw new InvalidOperationException("Backend is not started.");
        }

        if (controller < 1 || controller > ControllerCount)
        {
            throw new ArgumentOutOfRangeException(nameof(controller));
        }

        Reports.Add(state);
        if (!ReportsByController.TryGetValue(controller, out var reports))
        {
            reports = new List<GamepadState>();
            ReportsByController[controller] = reports;
        }

        reports.Add(state);
    }

    public void Stop() => IsConnected = false;

    public void Dispose() => Stop();
}
