using VirtualGamepadHost.Driver;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Runtime;

public sealed class ReportLoop
{
    private readonly StateStore _store;
    private readonly IXInputBackend _backend;
    private readonly TimeSpan _interval;

    public ReportLoop(StateStore store, IXInputBackend backend, TimeSpan? interval = null)
    {
        _store = store;
        _backend = backend;
        _interval = interval ?? TimeSpan.FromMilliseconds(8);
    }

    public void SubmitOnce() => _backend.Submit(_store.Snapshot());

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        using var timer = new PeriodicTimer(_interval);
        while (await timer.WaitForNextTickAsync(cancellationToken).ConfigureAwait(false))
        {
            SubmitOnce();
        }
    }
}
