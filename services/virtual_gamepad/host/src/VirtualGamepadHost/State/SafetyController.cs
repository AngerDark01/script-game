namespace VirtualGamepadHost.State;

public sealed class SafetyController
{
    private readonly StateStore _store;
    private readonly object _gate = new();
    private RunState _runState;

    public SafetyController(StateStore store)
    {
        _store = store;
        // A newly created Host must never begin consuming mapped physical
        // input.  Treat both controller slots as explicitly paused from their
        // first report, rather than using an ambiguous ready state.
        _runState = RunState.Paused;
        _store.SetPaused(true);
    }

    public RunState RunState
    {
        get
        {
            lock (_gate)
            {
                return _runState;
            }
        }
    }

    public void Start()
    {
        lock (_gate)
        {
            _runState = RunState.Running;
            _store.SetPaused(false);
        }
    }

    public void Pause()
    {
        lock (_gate)
        {
            _store.ClearAll();
            _runState = RunState.Paused;
            _store.SetPaused(true);
        }
    }

    public void TogglePause()
    {
        lock (_gate)
        {
            if (_runState == RunState.Running)
            {
                _store.ClearAll();
                _runState = RunState.Paused;
                _store.SetPaused(true);
            }
            else
            {
                _runState = RunState.Running;
                _store.SetPaused(false);
            }
        }
    }

    public void Reset()
    {
        lock (_gate)
        {
            _store.ClearAll();
            if (_runState == RunState.Paused)
            {
                _store.SetPaused(true);
            }
        }
    }

    public void EmergencyReset()
    {
        lock (_gate)
        {
            _store.ClearAll();
            _store.SetPaused(true);
            _runState = RunState.Paused;
        }
    }

    public void Fail()
    {
        lock (_gate)
        {
            _store.ClearAll();
            _store.SetPaused(true);
            _runState = RunState.Error;
        }
    }
}
