using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Input;
using VirtualGamepadHost.Protocol;
using VirtualGamepadHost.State;
using LanInputSync;

namespace VirtualGamepadHost.Runtime;

public sealed class HostComposition : IAsyncDisposable
{
    private readonly ControllerRegistry _registry;
    private readonly IXInputBackend _backend;
    private readonly ReportLoop _reportLoop;
    private readonly NamedPipeServer _pipeServer;
    private readonly RawInputCapture? _rawInput;
    private readonly DriverStatus _driverStatus;
    private readonly ILanSyncService? _sync;
    private readonly CancellationTokenSource _shutdown = new();
    private Task? _reportTask;
    private Task? _pipeTask;

    private HostComposition(ControllerRegistry registry, IXInputBackend backend, ReportLoop reportLoop, NamedPipeServer pipeServer, DriverStatus driverStatus, RawInputCapture? rawInput, ILanSyncService? sync)
    {
        _registry = registry;
        _backend = backend;
        _reportLoop = reportLoop;
        _pipeServer = pipeServer;
        _driverStatus = driverStatus;
        _rawInput = rawInput;
        _sync = sync;
    }

    public static HostComposition Create()
    {
        var probe = new ViGEmDriverProbe();
        var driverStatus = probe.Probe();
        IXInputBackend backend = driverStatus.Installed ? new ViGEmXInputBackend() : new NullXInputBackend();

        try
        {
            backend.Start();
        }
        catch (Exception ex)
        {
            backend.Dispose();
            backend = new NullXInputBackend();
            driverStatus = new DriverStatus(false, $"Virtual controllers unavailable: {ex.Message}");
        }

        var registry = ControllerRegistry.CreateDefault(backend);
        ILanSyncService? sync = null;
        string syncError = "";
        try
        {
            sync = new LanSyncService();
            registry.AttachSync(sync);
        }
        catch (Exception ex)
        {
            sync?.Dispose();
            sync = null;
            syncError = $" LAN sync unavailable: {ex.Message}";
        }
        RawInputCapture? rawInput = null;
        try
        {
            rawInput = new RawInputCapture(
                registry.ApplyPhysical,
                onHotkey: action =>
                {
                    switch (action)
                    {
                        case HotkeyAction.ToggleController1:
                            registry.ToggleController(1);
                            break;
                        case HotkeyAction.ToggleController2:
                            registry.ToggleController(2);
                            break;
                        case HotkeyAction.EmergencyResetAll:
                            registry.EmergencyResetAll();
                            break;
                    }
                },
                shouldSuppress: input =>
                    backend.IsConnected
                    && IsNotControlHotkey(input) && registry.ShouldSuppressPhysical(input));
            rawInput.Start();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Raw Input unavailable: {ex.Message}");
            rawInput?.Dispose();
            rawInput = null;
        }

        HostStatus Status()
        {
            var inputStatus = rawInput?.CaptureMode ?? "Input capture unavailable";
            var controllerStatuses = registry.Slots.Select(slot => new ControllerStatus(slot.Number, registry.EffectiveRunState(slot.Number), backend.IsConnected && slot.Number <= backend.ControllerCount, registry.EffectiveState(slot.Number), registry.IsRemote(slot.Number) ? "remote" : "local")).ToArray();
            var firstState = controllerStatuses.FirstOrDefault();
            return new(firstState?.RunState ?? RunState.Ready, driverStatus.Installed, backend.IsConnected, $"{driverStatus.Message} Input: {inputStatus}.{syncError}", controllerStatuses);
        }

        var router = new CommandRouter(registry, Status, () => backend.IsConnected);
        return new HostComposition(registry, backend, new ReportLoop(registry, backend), new NamedPipeServer(router), driverStatus, rawInput, sync);
    }

    private static bool IsNotControlHotkey(PhysicalInput input)
        => input.Source is not "keyboard:F7" and not "keyboard:F8" and not "keyboard:F9";

    public HostStatus Status
    {
        get
        {
            var statuses = _registry.Slots.Select(slot => new ControllerStatus(slot.Number, _registry.EffectiveRunState(slot.Number), _backend.IsConnected && slot.Number <= _backend.ControllerCount, _registry.EffectiveState(slot.Number), _registry.IsRemote(slot.Number) ? "remote" : "local")).ToArray();
            return new(statuses[0].RunState, _driverStatus.Installed, _backend.IsConnected, _driverStatus.Message, statuses);
        }
    }

    public Task RunAsync(CancellationToken cancellationToken = default)
    {
        var linked = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdown.Token);
        _reportTask = _reportLoop.RunAsync(linked.Token);
        _pipeTask = _pipeServer.RunAsync(linked.Token);
        return Task.WhenAll(_reportTask, _pipeTask);
    }

    public async ValueTask DisposeAsync()
    {
        _shutdown.Cancel();
        if (_reportTask is not null || _pipeTask is not null)
        {
            try
            {
                await Task.WhenAll(new[] { _reportTask, _pipeTask }.Where(task => task is not null)!).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
            }
        }

        _registry.EmergencyResetAll();
        _sync?.Dispose();
        _rawInput?.Dispose();
        _backend.Stop();
        _backend.Dispose();
        _shutdown.Dispose();
    }
}
