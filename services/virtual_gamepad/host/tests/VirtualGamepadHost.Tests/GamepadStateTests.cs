using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Tests;

public sealed class GamepadStateTests
{
    [Fact]
    public void NeutralStateStartsWithAllControlsReleased()
    {
        var state = GamepadState.Neutral;

        Assert.Equal((ushort)0, state.Buttons);
        Assert.Equal((byte)0, state.LeftTrigger);
        Assert.Equal((byte)0, state.RightTrigger);
        Assert.Equal((short)0, state.LeftStickX);
        Assert.Equal((short)0, state.RightStickY);
    }

    [Fact]
    public void ButtonCanBePressedAndReleased()
    {
        var pressed = GamepadState.Neutral.WithButton(GamepadButton.A, true);

        Assert.True(pressed.IsPressed(GamepadButton.A));
        Assert.False(pressed.WithButton(GamepadButton.A, false).IsPressed(GamepadButton.A));
    }

    [Fact]
    public void AxesAndTriggersAreClampedToDeviceRanges()
    {
        var state = GamepadState.Neutral
            .WithAxis(GamepadAxis.LeftX, 100_000)
            .WithAxis(GamepadAxis.RightY, -100_000)
            .WithTrigger(GamepadTrigger.Right, 1_000);

        Assert.Equal(short.MaxValue, state.LeftStickX);
        Assert.Equal(short.MinValue, state.RightStickY);
        Assert.Equal(byte.MaxValue, state.RightTrigger);
    }
}
