using LanInputSync;
using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Integration;

internal static class LanSyncAdapter
{
    public static PadState ToNetwork(GamepadState state) => new(state.Buttons, state.LeftTrigger,
        state.RightTrigger, state.LeftStickX, state.LeftStickY, state.RightStickX, state.RightStickY);
    public static GamepadState ToGamepad(PadState state) => new(state.Buttons, state.LeftTrigger,
        state.RightTrigger, state.LeftStickX, state.LeftStickY, state.RightStickX, state.RightStickY);
}
