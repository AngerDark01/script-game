namespace VirtualGamepadHost.State;

public sealed class SafetyController
{
    private readonly StateStore _store;

    public SafetyController(StateStore store)
    {
        _store = store;
        RunState = RunState.Ready;
    }

    public RunState RunState { get; private set; }

    public void Start()
    {
        RunState = RunState.Running;
        _store.SetPaused(false);
    }

    public void Pause()
    {
        RunState = RunState.Paused;
        _store.SetPaused(true);
    }

    public void TogglePause()
    {
        if (RunState == RunState.Running)
        {
            Pause();
        }
        else
        {
            Start();
        }
    }

    public void Reset()
    {
        _store.ClearAll();
        if (RunState == RunState.Paused)
        {
            _store.SetPaused(true);
        }
    }

    public void EmergencyReset()
    {
        _store.ClearAll();
        _store.SetPaused(true);
        RunState = RunState.Paused;
    }

    public void Fail()
    {
        _store.ClearAll();
        _store.SetPaused(true);
        RunState = RunState.Error;
    }
}
