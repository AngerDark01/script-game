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

    [Fact]
    public void SubmitAllIncludesNonExclusiveEventStateWhileControllerIsPaused()
    {
        var backend = new FakeXInputBackend(2);
        backend.Start();
        var registry = ControllerRegistry.CreateDefault(backend);
        registry.SetEventState(1, "event:local", new GamepadState((ushort)GamepadButton.A, 0, 0, 0, 0, 0, 0), TimeSpan.FromSeconds(1));

        registry.SubmitAll();

        Assert.True(backend.ReportsByController[1].Last().IsPressed(GamepadButton.A));
    }

    [Fact]
    public void LocalMappingAndEventStateAreMergedAndClearedIndependently()
    {
        var backend = new FakeXInputBackend(2);
        backend.Start();
        var registry = ControllerRegistry.CreateDefault(backend);
        registry[1].Safety.Start();

        registry[1].Mapping.Apply(new PhysicalInput("keyboard:W", PhysicalInputType.KeyDown));
        registry.SetEventState(1, "event:remote", GamepadState.Neutral.WithButton(GamepadButton.X, true), TimeSpan.FromSeconds(1));

        var merged = registry.EffectiveState(1);
        Assert.Equal(short.MaxValue, merged.LeftStickY);
        Assert.True(merged.IsPressed(GamepadButton.X));

        registry.ClearEventState(1, "event:remote");

        var mappingOnly = registry.EffectiveState(1);
        Assert.Equal(short.MaxValue, mappingOnly.LeftStickY);
        Assert.False(mappingOnly.IsPressed(GamepadButton.X));
    }

    [Fact]
    public void SubmitAllAcceptsMinimumAxisValueWithoutStoppingReports()
    {
        var backend = new FakeXInputBackend(2);
        backend.Start();
        var registry = ControllerRegistry.CreateDefault(backend);
        registry.SetEventState(1, "event:local", new GamepadState(0, 0, 0, short.MinValue, 0, 0, 0), TimeSpan.FromSeconds(1));

        registry.SubmitAll();

        Assert.Equal(short.MinValue, backend.ReportsByController[1].Last().LeftStickX);
    }

    private static ControllerSlot NewSlot(int number)
    {
        var store = new StateStore();
        return new ControllerSlot(number, store, new SafetyController(store), new MappingEngine(store));
    }
}
