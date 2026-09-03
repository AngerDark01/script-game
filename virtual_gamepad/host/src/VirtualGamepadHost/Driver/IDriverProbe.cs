namespace VirtualGamepadHost.Driver;

public sealed record DriverStatus(bool Installed, string Message);

public interface IDriverProbe
{
    DriverStatus Probe();
}
