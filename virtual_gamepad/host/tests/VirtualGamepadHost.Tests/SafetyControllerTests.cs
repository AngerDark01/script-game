using VirtualGamepadHost.Model;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Tests;

public sealed class SafetyControllerTests
{
    [Fact]
    public void NewControllerStartsPausedAndNeutral()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);

        Assert.Equal(RunState.Paused, safety.RunState);
        Assert.Equal(GamepadState.Neutral, store.Snapshot());
    }

    [Fact]
    public void EmergencyResetClearsInputsAndPauses()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        safety.Start();
        store.SetButton("test", GamepadButton.A, true);

        safety.EmergencyReset();

        Assert.Equal(RunState.Paused, safety.RunState);
        Assert.Equal(GamepadState.Neutral, store.Snapshot());
    }

    [Fact]
    public void TogglePauseSwitchesBetweenRunningAndPaused()
    {
        var safety = new SafetyController(new StateStore());

        safety.TogglePause();
        Assert.Equal(RunState.Running, safety.RunState);
        safety.TogglePause();
        Assert.Equal(RunState.Paused, safety.RunState);
    }
}
