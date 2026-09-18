namespace VirtualGamepadHost.Input;

public enum PhysicalInputType
{
    KeyDown,
    KeyUp,
    MouseButtonDown,
    MouseButtonUp,
    MouseMove,
}

public sealed record PhysicalInput(
    string Source,
    PhysicalInputType Type,
    int DeltaX = 0,
    int DeltaY = 0);
