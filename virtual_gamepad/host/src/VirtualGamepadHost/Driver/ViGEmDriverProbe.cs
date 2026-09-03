using Nefarius.ViGEm.Client;
using Nefarius.ViGEm.Client.Exceptions;

namespace VirtualGamepadHost.Driver;

public sealed class ViGEmDriverProbe : IDriverProbe
{
    public DriverStatus Probe()
    {
        try
        {
            using var client = new ViGEmClient();
            return new DriverStatus(true, "ViGEmBus is available.");
        }
        catch (VigemBusNotFoundException)
        {
            return new DriverStatus(false, "ViGEmBus is not installed. Install the signed ViGEmBus driver first.");
        }
        catch (Exception ex)
        {
            return new DriverStatus(false, $"ViGEmBus probe failed: {ex.Message}");
        }
    }
}
