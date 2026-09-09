namespace VirtualGamepadHost.Runtime;

public sealed class RemoteOwnershipException(int controller) : InvalidOperationException(
    $"Controller {controller} is owned by remote reception. Switch it to local mode before sending local actions.");
