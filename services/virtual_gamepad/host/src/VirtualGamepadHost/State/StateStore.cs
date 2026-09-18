using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.State;

/// <summary>
/// Thread-safe source arbitration. Button sources are ORed, triggers use the
/// strongest value, and axes use the source with the strongest magnitude.
/// </summary>
public sealed class StateStore
{
    private sealed class SourceEntry
    {
        public GamepadState State = GamepadState.Neutral;
        public DateTime? ExpiresAtUtc;
        public long Sequence;
    }

    private readonly object _gate = new();
    private readonly Dictionary<string, SourceEntry> _sources = new(StringComparer.Ordinal);
    private bool _paused;
    private long _sequence;

    public TimeSpan DefaultTtl { get; }

    public StateStore(TimeSpan? defaultTtl = null)
    {
        DefaultTtl = defaultTtl ?? TimeSpan.FromMilliseconds(500);
    }

    public GamepadState Snapshot()
    {
        lock (_gate)
        {
            RemoveExpired(DateTime.UtcNow);
            return _paused ? GamepadState.Neutral : MergeSources();
        }
    }

    public void SetButton(string source, GamepadButton button, bool pressed, TimeSpan? ttl = null)
    {
        Update(source, state => state.WithButton(button, pressed), ttl);
    }

    public void SetAxis(string source, GamepadAxis axis, int value, TimeSpan? ttl = null)
    {
        Update(source, state => state.WithAxis(axis, value), ttl);
    }

    public void SetTrigger(string source, GamepadTrigger trigger, int value, TimeSpan? ttl = null)
    {
        Update(source, state => state.WithTrigger(trigger, value), ttl);
    }

    public void SetState(string source, GamepadState state, TimeSpan? ttl = null)
    {
        if (string.IsNullOrWhiteSpace(source))
        {
            throw new ArgumentException("Source is required.", nameof(source));
        }

        lock (_gate)
        {
            var entry = GetOrCreate(source);
            entry.State = state;
            entry.ExpiresAtUtc = ttl is null ? null : DateTime.UtcNow + ttl.Value;
            entry.Sequence = ++_sequence;
        }
    }

    public void ClearSource(string source)
    {
        lock (_gate)
        {
            _sources.Remove(source);
        }
    }

    public void ClearAll()
    {
        lock (_gate)
        {
            _sources.Clear();
        }
    }

    public void ClearSources(string prefix)
    {
        lock (_gate)
        {
            foreach (var source in _sources.Keys.Where(source => source.StartsWith(prefix, StringComparison.Ordinal)).ToArray())
            {
                _sources.Remove(source);
            }
        }
    }

    public void SetPaused(bool paused)
    {
        lock (_gate)
        {
            _paused = paused;
        }
    }

    public bool IsPaused
    {
        get
        {
            lock (_gate)
            {
                return _paused;
            }
        }
    }

    public void Heartbeat(string source, TimeSpan? ttl = null)
    {
        lock (_gate)
        {
            var entry = GetOrCreate(source);
            entry.ExpiresAtUtc = ttl is null ? null : DateTime.UtcNow + ttl.Value;
            entry.Sequence = ++_sequence;
        }
    }

    private void Update(string source, Func<GamepadState, GamepadState> update, TimeSpan? ttl)
    {
        if (string.IsNullOrWhiteSpace(source))
        {
            throw new ArgumentException("Source is required.", nameof(source));
        }

        lock (_gate)
        {
            var entry = GetOrCreate(source);
            entry.State = update(entry.State);
            entry.ExpiresAtUtc = DateTime.UtcNow + (ttl ?? DefaultTtl);
            entry.Sequence = ++_sequence;
        }
    }

    private SourceEntry GetOrCreate(string source)
    {
        if (string.IsNullOrWhiteSpace(source))
        {
            throw new ArgumentException("Source is required.", nameof(source));
        }

        if (!_sources.TryGetValue(source, out var entry))
        {
            entry = new SourceEntry();
            _sources[source] = entry;
        }

        return entry;
    }

    private void RemoveExpired(DateTime nowUtc)
    {
        foreach (var source in _sources
                     .Where(pair => pair.Value.ExpiresAtUtc is not null && pair.Value.ExpiresAtUtc <= nowUtc)
                     .Select(pair => pair.Key)
                     .ToArray())
        {
            _sources.Remove(source);
        }
    }

    private GamepadState MergeSources()
    {
        ushort buttons = 0;
        byte leftTrigger = 0;
        byte rightTrigger = 0;
        short leftX = StrongestAxis(GamepadAxis.LeftX);
        short leftY = StrongestAxis(GamepadAxis.LeftY);
        short rightX = StrongestAxis(GamepadAxis.RightX);
        short rightY = StrongestAxis(GamepadAxis.RightY);

        foreach (var entry in _sources.Values)
        {
            buttons |= entry.State.Buttons;
            leftTrigger = Math.Max(leftTrigger, entry.State.LeftTrigger);
            rightTrigger = Math.Max(rightTrigger, entry.State.RightTrigger);
        }

        return new GamepadState(buttons, leftTrigger, rightTrigger, leftX, leftY, rightX, rightY);
    }

    private short StrongestAxis(GamepadAxis axis)
    {
        return _sources.Values
            .Select(entry => (value: AxisValue(entry.State, axis), entry.Sequence))
            .OrderByDescending(item => Math.Abs((int)item.value))
            .ThenByDescending(item => item.Sequence)
            .Select(item => item.value)
            .FirstOrDefault();
    }

    private static short AxisValue(GamepadState state, GamepadAxis axis) => axis switch
    {
        GamepadAxis.LeftX => state.LeftStickX,
        GamepadAxis.LeftY => state.LeftStickY,
        GamepadAxis.RightX => state.RightStickX,
        GamepadAxis.RightY => state.RightStickY,
        _ => 0,
    };
}
