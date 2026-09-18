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
    public void ProfileMouseSensitivityAndStickClickAliasesReachDeviceBindings()
    {
        using var document = JsonDocument.Parse("""
            {
              "mouseSensitivity": 4.0,
              "bindings": {
                "RightStick": ["mouse:move_x"],
                "LeftStickClick": ["keyboard:C"],
                "RightStickClick": ["keyboard:V"]
              }
            }
            """);
        var config = MappingConfig.FromJson(document.RootElement);

        Assert.Contains(config.Bindings, binding => binding.Source == "mouse:move_x" && binding.Target == "axis:RightX" && binding.Sensitivity == 4.0);
        Assert.Contains(config.Bindings, binding => binding.Source == "keyboard:C" && binding.Target == "button:LeftThumb");
        Assert.Contains(config.Bindings, binding => binding.Source == "keyboard:V" && binding.Target == "button:RightThumb");
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

    [Fact]
    public async Task ReleasingDiagonalKeyKeepsOtherHeldAxisActivePastInputTtl()
    {
        var store = new StateStore(TimeSpan.FromMilliseconds(15));
        var engine = new MappingEngine(store, new MappingConfig(new[]
        {
            new Binding("keyboard:W", "axis:LeftY", 1),
            new Binding("keyboard:D", "axis:LeftX", 1),
        }));

        engine.Apply(new PhysicalInput("keyboard:W", PhysicalInputType.KeyDown));
        engine.Apply(new PhysicalInput("keyboard:D", PhysicalInputType.KeyDown));
        engine.Apply(new PhysicalInput("keyboard:D", PhysicalInputType.KeyUp));

        await Task.Delay(40);

        var state = store.Snapshot();
        Assert.Equal((short)0, state.LeftStickX);
        Assert.Equal(short.MaxValue, state.LeftStickY);
    }

    [Fact]
    public void SuppressionMatchesConfiguredKeyboardAndMouseSources()
    {
        var engine = new MappingEngine(new StateStore(), new MappingConfig(new[]
        {
            new Binding("keyboard:J", "button:A"),
            new Binding("mouse:left", "trigger:Right"),
            new Binding("mouse:move_x", "axis:RightX"),
        }, MouseMovePassthrough: false));

        Assert.True(engine.ShouldSuppress(new PhysicalInput("keyboard:J", PhysicalInputType.KeyDown)));
        // Event trigger keys must remain available when they are not part of
        // the active gamepad mapping. F5 is the local event test shortcut.
        Assert.False(engine.ShouldSuppress(new PhysicalInput("keyboard:F5", PhysicalInputType.KeyDown)));
        Assert.False(engine.ShouldSuppress(new PhysicalInput("keyboard:K", PhysicalInputType.KeyDown)));
        Assert.True(engine.ShouldSuppress(new PhysicalInput("mouse:left", PhysicalInputType.MouseButtonDown)));
        Assert.True(engine.ShouldSuppress(new PhysicalInput("mouse", PhysicalInputType.MouseMove, DeltaX: 2)));
        Assert.False(engine.ShouldSuppress(new PhysicalInput("mouse", PhysicalInputType.MouseMove, DeltaY: 2)));
    }

    [Fact]
    public void MouseMovePassthroughDefaultsToEnabledForExistingProfiles()
    {
        using var document = JsonDocument.Parse("{}");

        var config = MappingConfig.FromJson(document.RootElement);

        Assert.True(config.MouseMovePassthrough);
    }

    [Fact]
    public void MouseMovementCanPassThroughWhileStillDrivingRightStick()
    {
        var store = new StateStore();
        var engine = new MappingEngine(store, new MappingConfig(
            new[] { new Binding("mouse:move_x", "axis:RightX", Sensitivity: 4.0) },
            MouseMovePassthrough: true));
        var input = new PhysicalInput("mouse", PhysicalInputType.MouseMove, DeltaX: 2);

        engine.Apply(input);

        Assert.False(engine.ShouldSuppress(input));
        Assert.Equal((short)9600, store.Snapshot().RightStickX);
    }
}
