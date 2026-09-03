using VirtualGamepadHost.Input;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.State;
using System.Text.Json;

namespace VirtualGamepadHost.Tests;

public sealed class MappingEngineTests
{
    [Fact]
    public void KeyboardBindingPressesAndReleasesVirtualButton()
    {
        var store = new StateStore();
        var engine = new MappingEngine(store, new MappingConfig(new[] { new Binding("keyboard:Space", "button:A") }));

        engine.Apply(new PhysicalInput("keyboard:Space", PhysicalInputType.KeyDown));
        Assert.True(store.Snapshot().IsPressed(GamepadButton.A));
        engine.Apply(new PhysicalInput("keyboard:Space", PhysicalInputType.KeyUp));
        Assert.False(store.Snapshot().IsPressed(GamepadButton.A));
    }

    [Fact]
    public void DigitalAxisBindingMapsDirectionAndMouseMoveUsesRelativeDelta()
    {
        var store = new StateStore();
        var engine = new MappingEngine(store, new MappingConfig(new[]
        {
            new Binding("keyboard:W", "axis:LeftY", 1),
            new Binding("mouse:move_x", "axis:RightX", Sensitivity: 0.5),
        }));

        engine.Apply(new PhysicalInput("keyboard:W", PhysicalInputType.KeyDown));
        Assert.Equal(short.MaxValue, store.Snapshot().LeftStickY);
        engine.Apply(new PhysicalInput("mouse", PhysicalInputType.MouseMove, DeltaX: 10));
        Assert.Equal((short)6000, store.Snapshot().RightStickX);
    }

    [Fact]
    public void UiFriendlyAliasesExpandToDeviceTargets()
    {
        using var document = JsonDocument.Parse("{\"bindings\":{\"A\":[\"keyboard:Space\"],\"LeftStick\":[\"keyboard:W\"]}}");
        var config = MappingConfig.FromJson(document.RootElement);

        Assert.Contains(config.Bindings, binding => binding.Target == "button:A");
        Assert.Contains(config.Bindings, binding => binding.Target == "axis:LeftY" && binding.Value > 0);
    }

    [Fact]
    public void ReleasingOneOfTwoOpposingKeysKeepsTheOtherAxisActive()
    {
        var store = new StateStore();
        var engine = new MappingEngine(store, new MappingConfig(new[]
        {
            new Binding("keyboard:W", "axis:LeftY", 1),
            new Binding("keyboard:S", "axis:LeftY", -1),
        }));

        engine.Apply(new PhysicalInput("keyboard:W", PhysicalInputType.KeyDown));
        engine.Apply(new PhysicalInput("keyboard:S", PhysicalInputType.KeyDown));
        engine.Apply(new PhysicalInput("keyboard:S", PhysicalInputType.KeyUp));

        Assert.Equal(short.MaxValue, store.Snapshot().LeftStickY);
    }
}
