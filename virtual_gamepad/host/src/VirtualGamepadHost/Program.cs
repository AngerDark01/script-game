using VirtualGamepadHost.Protocol;
using VirtualGamepadHost.Runtime;

if (args.Contains("--help", StringComparer.OrdinalIgnoreCase))
{
    Console.WriteLine("VirtualGamepadHost - Xbox 360 XInput virtual controller host");
    Console.WriteLine("  --help     Show this help");
    Console.WriteLine("  --version  Show the host version");
    return;
}

if (args.Contains("--version", StringComparer.OrdinalIgnoreCase))
{
    Console.WriteLine("VirtualGamepadHost 0.1.0");
    return;
}

if (!Elevation.EnsureAdministrator(args, Console.Error.WriteLine))
{
    return;
}

await using var host = HostComposition.Create();
Console.WriteLine($"Driver: {(host.Status.DriverInstalled ? "ready" : "missing")}");
Console.WriteLine($"Device: {(host.Status.DeviceConnected ? "connected" : "unavailable")}");
Console.WriteLine($"Pipe: {NamedPipeServer.PipeName}");
Console.WriteLine("Press Ctrl+C to exit.");

using var shutdown = new CancellationTokenSource();
Console.CancelKeyPress += (_, eventArgs) =>
{
    eventArgs.Cancel = true;
    shutdown.Cancel();
};

try
{
    await host.RunAsync(shutdown.Token);
}
catch (OperationCanceledException)
{
    // Normal Ctrl+C shutdown.
}
