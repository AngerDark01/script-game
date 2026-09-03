using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Input;
using VirtualGamepadHost.Protocol;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Runtime;

public sealed class HostComposition : IAsyncDisposable
{
    private readonly StateStore _store;
    private readonly SafetyController _safety;
    private readonly IXInputBackend _backend;
    private readonly ReportLoop _reportLoop;
    private readonly NamedPipeServer _pipeServer;
    private readonly MappingEngine _mapping;
    private readonly RawInputCapture? _rawInput;
    private readonly DriverStatus _driverStatus;
    private readonly CancellationTokenSource _shutdown = new();
    private Task? _reportTask;
    private Task? _pipeTask;

    private HostComposition(
        StateStore store,
        SafetyController safety,
        IXInputBackend backend,
        ReportLoop reportLoop,
        NamedPipeServer pipeServer,
        DriverStatus driverStatus,
        MappingEngine mapping,
        RawInputCapture? rawInput)
    {
        _store = store;
        _safety = safety;
        _backend = backend;
        _reportLoop = reportLoop;
        _pipeServer = pipeServer;
        _driverStatus = driverStatus;
        _mapping = mapping;
        _rawInput = rawInput;
    }

    public static HostComposition Create()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var mapping = new MappingEngine(store);
        RawInputCapture? rawInput = null;
        try
        {
            rawInput = new RawInputCapture(
                mapping.Apply,
                action =>
                {
                    if (action == HotkeyAction.TogglePause)
                    {
                        safety.TogglePause();
                    }
                    else
                    {
                        safety.EmergencyReset();
                    }
                });
            rawInput.Start();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Raw Input unavailable: {ex.Message}");
            rawInput?.Dispose();
            rawInput = null;
        }
        var probe = new ViGEmDriverProbe();
        var driverStatus = probe.Probe();
        IXInputBackend backend = driverStatus.Installed
            ? new ViGEmXInputBackend()
            : new NullXInputBackend();

        try
        {
            backend.Start();
        }
        catch (Exception ex)
        {
            backend.Dispose();
            backend = new NullXInputBackend();
            driverStatus = new DriverStatus(false, $"Virtual controller unavailable: {ex.Message}");
        }

        var reportLoop = new ReportLoop(store, backend);
        HostStatus Status() => new(safety.RunState, driverStatus.Installed, backend.IsConnected, driverStatus.Message);
        var router = new CommandRouter(store, safety, Status, mapping, () => backend.IsConnected);
        return new HostComposition(store, safety, backend, reportLoop, new NamedPipeServer(router), driverStatus, mapping, rawInput);
    }

    public HostStatus Status => new(
        _safety.RunState,
        _driverStatus.Installed,
        _backend.IsConnected,
        _driverStatus.Message);

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
                // Expected during normal shutdown.
            }
        }

        _safety.EmergencyReset();
        _rawInput?.Dispose();
        _backend.Stop();
        _backend.Dispose();
        _shutdown.Dispose();
    }
}
