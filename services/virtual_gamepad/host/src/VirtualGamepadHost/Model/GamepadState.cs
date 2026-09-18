namespace VirtualGamepadHost.Model;

public sealed record GamepadState(
    ushort Buttons,
    byte LeftTrigger,
    byte RightTrigger,
    short LeftStickX,
    short LeftStickY,
    short RightStickX,
    short RightStickY)
{
    public static GamepadState Neutral => new(0, 0, 0, 0, 0, 0, 0);

    public bool IsPressed(GamepadButton button) => (Buttons & (ushort)button) != 0;

    public GamepadState WithButton(GamepadButton button, bool pressed)
    {
        var buttons = pressed
            ? (ushort)(Buttons | (ushort)button)
            : (ushort)(Buttons & ~(ushort)button);
        return this with { Buttons = buttons };
    }

    public GamepadState WithAxis(GamepadAxis axis, int value)
    {
        var clamped = Math.Clamp(value, short.MinValue, short.MaxValue);
        return axis switch
        {
            GamepadAxis.LeftX => this with { LeftStickX = (short)clamped },
            GamepadAxis.LeftY => this with { LeftStickY = (short)clamped },
            GamepadAxis.RightX => this with { RightStickX = (short)clamped },
            GamepadAxis.RightY => this with { RightStickY = (short)clamped },
            _ => throw new ArgumentOutOfRangeException(nameof(axis), axis, null),
        };
    }

    public GamepadState WithTrigger(GamepadTrigger trigger, int value)
    {
        var clamped = Math.Clamp(value, byte.MinValue, byte.MaxValue);
        return trigger switch
        {
            GamepadTrigger.Left => this with { LeftTrigger = (byte)clamped },
            GamepadTrigger.Right => this with { RightTrigger = (byte)clamped },
            _ => throw new ArgumentOutOfRangeException(nameof(trigger), trigger, null),
        };
    }
}
