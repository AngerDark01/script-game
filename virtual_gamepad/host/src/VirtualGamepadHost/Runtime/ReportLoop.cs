using VirtualGamepadHost.Driver;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Runtime;

public sealed class ReportLoop
{
    private readonly ControllerRegistry? _registry;
    private readonly StateStore? _store;
    private readonly IXInputBackend _backend;
    private readonly TimeSpan _interval;

    public ReportLoop(StateStore store, IXInputBackend backend, TimeSpan? interval = null)
    {
        _store = store;
        _backend = backend;
        _interval = interval ?? TimeSpan.FromMilliseconds(8);
    }

    public ReportLoop(ControllerRegistry registry, IXInputBackend backend, TimeSpan? interval = null)
    {
        _registry = registry;
        _backend = backend;
        _interval = interval ?? TimeSpan.FromMilliseconds(8);
    }

    public void SubmitOnce()
    {
        if (_registry is not null)
        {
            _registry.SubmitAll();
            return;
        }

        _backend.Submit(1, _store!.Snapshot());
    }

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        using var timer = new PeriodicTimer(_interval);
        while (await timer.WaitForNextTickAsync(cancellationToken).ConfigureAwait(false))
        {
            SubmitOnce();
        }
    }
}
