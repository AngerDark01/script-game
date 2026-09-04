using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Input;
using VirtualGamepadHost.Protocol;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Runtime;

public sealed class HostComposition : IAsyncDisposable
{
    private readonly ControllerRegistry _registry;
    private readonly IXInputBackend _backend;
    private readonly ReportLoop _reportLoop;
    private readonly NamedPipeServer _pipeServer;
    private readonly RawInputCapture? _rawInput;
    private readonly DriverStatus _driverStatus;
    private readonly CancellationTokenSource _shutdown = new();
    private Task? _reportTask;
    private Task? _pipeTask;

    private HostComposition(ControllerRegistry registry, IXInputBackend backend, ReportLoop reportLoop, NamedPipeServer pipeServer, DriverStatus driverStatus, RawInputCapture? rawInput)
    {
        _registry = registry;
        _backend = backend;
        _reportLoop = reportLoop;
        _pipeServer = pipeServer;
        _driverStatus = driverStatus;
        _rawInput = rawInput;
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
        RawInputCapture? rawInput = null;
        try
        {
            rawInput = new RawInputCapture(
                input =>
                {
                    foreach (var slot in registry.Slots.Where(slot => slot.Safety.RunState == RunState.Running))
                    {
                        slot.Mapping.Apply(input);
                    }
                },
                onHotkey: action =>
                {
                    switch (action)
                    {
                        case HotkeyAction.ToggleController1:
                            registry[1].Safety.TogglePause();
                            break;
                        case HotkeyAction.ToggleController2:
                            registry[2].Safety.TogglePause();
                            break;
                        case HotkeyAction.EmergencyResetAll:
                            registry.EmergencyResetAll();
                            break;
                    }
                },
                shouldSuppress: input =>
                    backend.IsConnected
                    && registry.Slots.Any(slot => slot.Safety.RunState == RunState.Running && IsNotControlHotkey(input) && slot.Mapping.ShouldSuppress(input)));
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
            var controllerStatuses = registry.Slots.Select(slot => new ControllerStatus(slot.Number, slot.Safety.RunState, backend.IsConnected && slot.Number <= backend.ControllerCount, slot.Store.Snapshot())).ToArray();
            var firstState = controllerStatuses.FirstOrDefault();
            return new(firstState?.RunState ?? RunState.Ready, driverStatus.Installed, backend.IsConnected, $"{driverStatus.Message} Input: {inputStatus}.", controllerStatuses);
        }

        var router = new CommandRouter(registry, Status, () => backend.IsConnected);
        return new HostComposition(registry, backend, new ReportLoop(registry, backend), new NamedPipeServer(router), driverStatus, rawInput);
    }

    private static bool IsNotControlHotkey(PhysicalInput input)
        => input.Source is not "keyboard:F7" and not "keyboard:F8" and not "keyboard:F9";

    public HostStatus Status
    {
        get
        {
            var statuses = _registry.Slots.Select(slot => new ControllerStatus(slot.Number, slot.Safety.RunState, _backend.IsConnected && slot.Number <= _backend.ControllerCount, slot.Store.Snapshot())).ToArray();
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
        _rawInput?.Dispose();
        _backend.Stop();
        _backend.Dispose();
        _shutdown.Dispose();
    }
}
