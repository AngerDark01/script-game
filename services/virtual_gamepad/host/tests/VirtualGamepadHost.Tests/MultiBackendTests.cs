using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Tests;

public sealed class MultiBackendTests
{
    [Fact]
    public void BackendSubmitsIndependentReportsForEachController()
    {
        var backend = new FakeXInputBackend(controllerCount: 2);
        backend.Start();

        backend.Submit(1, GamepadState.Neutral.WithButton(GamepadButton.A, true));
        backend.Submit(2, GamepadState.Neutral.WithButton(GamepadButton.B, true));

        Assert.True(backend.ReportsByController[1].Last().IsPressed(GamepadButton.A));
        Assert.False(backend.ReportsByController[1].Last().IsPressed(GamepadButton.B));
        Assert.True(backend.ReportsByController[2].Last().IsPressed(GamepadButton.B));
        Assert.False(backend.ReportsByController[2].Last().IsPressed(GamepadButton.A));
    }
}
