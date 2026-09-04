using VirtualGamepadHost.Input;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.Runtime;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Tests;

public sealed class ControllerRegistryTests
{
    [Fact]
    public void SlotStatesDoNotBleedAcrossControllers()
    {
        var first = NewSlot(1);
        var second = NewSlot(2);
        var registry = new ControllerRegistry(new[] { first, second });

        first.Safety.Start();
        second.Safety.Start();
        first.Store.SetButton("test", GamepadButton.A, true);

        Assert.True(registry[1].Store.Snapshot().IsPressed(GamepadButton.A));
        Assert.False(registry[2].Store.Snapshot().IsPressed(GamepadButton.A));
    }

    [Fact]
    public void EmergencyResetAllPausesAndNeutralisesBothSlots()
    {
        var first = NewSlot(1);
        var second = NewSlot(2);
        var registry = new ControllerRegistry(new[] { first, second });
        first.Safety.Start();
        second.Safety.Start();
        first.Store.SetButton("test", GamepadButton.A, true);
        second.Store.SetButton("test", GamepadButton.B, true);

        registry.EmergencyResetAll();

        Assert.Equal(RunState.Paused, first.Safety.RunState);
        Assert.Equal(RunState.Paused, second.Safety.RunState);
        Assert.Equal(GamepadState.Neutral, first.Store.Snapshot());
        Assert.Equal(GamepadState.Neutral, second.Store.Snapshot());
    }

    private static ControllerSlot NewSlot(int number)
    {
        var store = new StateStore();
        return new ControllerSlot(number, store, new SafetyController(store), new MappingEngine(store));
    }
}
