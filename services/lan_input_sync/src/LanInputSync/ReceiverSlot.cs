namespace LanInputSync;

/// <summary>Used under service state lock. Time is supplied in monotonic milliseconds.</summary>
internal sealed class ReceiverSlot
{
    private readonly Queue<(ushort Buttons, long Time)> _buttons = new();
    public PadState Latest { get; private set; } = PadState.Neutral;
    public PadState Output { get; private set; } = PadState.Neutral;
    public uint Revision { get; private set; }
    public uint Epoch { get; private set; }
    public bool Enabled { get; private set; }
    public long LastSnapshot { get; private set; }
    public long GapSince { get; private set; }
    public int QueueLength => _buttons.Count;
    public void Reset()
    {
        Latest = Output = PadState.Neutral;
        _buttons.Clear(); Revision = Epoch = 0; Enabled = false; LastSnapshot = GapSince = 0;
    }
    public bool Transition(uint epoch, uint revision, bool enabled, ushort buttons, long now)
    {
        if (epoch < Epoch || (epoch == Epoch && revision <= Revision)) return true;
        if (epoch == Epoch && revision != Revision + 1) return false;
        if (epoch > Epoch)
        {
            _buttons.Clear(); Output = PadState.Neutral;
            Epoch = epoch;
        }
        Enabled = enabled; Revision = revision;
        if (!enabled) { _buttons.Clear(); Latest = Output = PadState.Neutral; return true; }
        if (_buttons.Count >= 32) return false;
        _buttons.Enqueue((buttons, now));
        GapSince = 0;
        return true;
    }
    public void Snapshot(uint epoch, uint revision, bool enabled, PadState state, long now)
    {
        if (epoch < Epoch) return;
        LastSnapshot = now;
        // A disabled snapshot may neutralize immediately but can never re-enable a route.
        if (!enabled && epoch >= Epoch)
        {
            Epoch = epoch; Revision = Math.Max(Revision, revision); Enabled = false;
            _buttons.Clear(); Latest = Output = PadState.Neutral; return;
        }
        Latest = state;
        if ((epoch > Epoch || revision > Revision) && GapSince == 0) GapSince = now;
    }
    public bool IsExpired(long now, int timeout) =>
        (LastSnapshot > 0 && now - LastSnapshot > timeout) ||
        (GapSince > 0 && now - GapSince > timeout) ||
        (_buttons.TryPeek(out var oldest) && now - oldest.Time > timeout);
    public PadState Consume()
    {
        if (!Enabled) return Output = PadState.Neutral;
        ushort buttons = _buttons.TryDequeue(out var next) ? next.Buttons : Output.Buttons;
        return Output = Latest with { Buttons = buttons };
    }
}
