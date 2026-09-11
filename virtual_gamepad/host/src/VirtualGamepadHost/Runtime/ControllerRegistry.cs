using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.Input;
using VirtualGamepadHost.Integration;
using VirtualGamepadHost.State;
using LanInputSync;
using System.Text.Json;

namespace VirtualGamepadHost.Runtime;

public sealed partial class ControllerRegistry
{
    private readonly Dictionary<int, ControllerSlot> _slots;
    private readonly IXInputBackend? _backend;
    private readonly object _routingGate = new();
    private readonly Dictionary<int, GamepadState> _lastRemote = new();
    private ILanSyncService? _sync;
    private readonly Dictionary<string, long> _syncCommandSequences = new();
    private readonly Dictionary<int, StateStore> _eventStores = new();

    public void AttachSync(ILanSyncService sync)
    {
        lock (_routingGate)
        {
            if (_sync is not null) throw new InvalidOperationException("Sync service is already attached.");
            _sync = sync;
        }
    }

    public bool IsRemote(int number) => _sync?.OwnsController(number) == true;

    public RunState EffectiveRunState(int number) => IsRemote(number)
        ? (_sync!.IsRemoteActive(number) ? RunState.Running : RunState.Paused)
        : IsProgram(number) ? RunState.Running : Get(number).Safety.RunState;

    public GamepadState EffectiveState(int number)
    {
        lock (_routingGate)
        {
            var baseState = IsRemote(number)
                ? (_sync!.IsRemoteActive(number) ? _lastRemote.GetValueOrDefault(number, GamepadState.Neutral) : GamepadState.Neutral)
                : LocalState(number);
            return Merge(baseState, _eventStores.TryGetValue(number, out var events) ? events.Snapshot() : GamepadState.Neutral);
        }
    }

    public void SetEventState(int number, string source, GamepadState state, TimeSpan? ttl)
    {
        lock (_routingGate)
        {
            if (IsRemote(number)) throw new RemoteOwnershipException(number);
            if (!_eventStores.TryGetValue(number, out var store))
                _eventStores[number] = store = new StateStore();
            store.SetState(source.StartsWith("event:", StringComparison.Ordinal) ? source : $"event:{source}", state, ttl);
        }
    }

    public void ClearEventState(int number, string? source)
    {
        lock (_routingGate)
        {
            if (!_eventStores.TryGetValue(number, out var store)) return;
            if (string.IsNullOrWhiteSpace(source)) store.ClearAll();
            else store.ClearSource(source.StartsWith("event:", StringComparison.Ordinal) ? source : $"event:{source}");
        }
    }

    private static GamepadState Merge(GamepadState a, GamepadState b)
        => new((ushort)(a.Buttons | b.Buttons), Math.Max(a.LeftTrigger, b.LeftTrigger), Math.Max(a.RightTrigger, b.RightTrigger),
            Math.Abs(a.LeftStickX) >= Math.Abs(b.LeftStickX) ? a.LeftStickX : b.LeftStickX,
            Math.Abs(a.LeftStickY) >= Math.Abs(b.LeftStickY) ? a.LeftStickY : b.LeftStickY,
            Math.Abs(a.RightStickX) >= Math.Abs(b.RightStickX) ? a.RightStickX : b.RightStickX,
            Math.Abs(a.RightStickY) >= Math.Abs(b.RightStickY) ? a.RightStickY : b.RightStickY);

    public void ApplyPhysical(PhysicalInput input)
    {
        lock (_routingGate)
            foreach (var slot in _slots.Values)
                if (!IsRemote(slot.Number) && slot.Safety.RunState == RunState.Running)
                    slot.Mapping.Apply(input);
    }

    public bool ShouldSuppressPhysical(PhysicalInput input)
    {
        lock (_routingGate)
            return _slots.Values.Any(slot => !IsRemote(slot.Number)
                && slot.Safety.RunState == RunState.Running && slot.Mapping.ShouldSuppress(input));
    }

    public void ExecuteLocal(int number, Action<ControllerSlot> action)
    {
        lock (_routingGate)
        {
            if (IsRemote(number)) throw new RemoteOwnershipException(number);
            if (ProgramLease(number) is not null) throw new InvalidOperationException("Controller is owned by a program session.");
            action(Get(number));
        }
    }

    public void Lifecycle(int number, string action)
    {
        lock (_routingGate)
        {
            var slot = Get(number);
            RevokeProgram(number);
            if (IsRemote(number))
            {
                slot.Safety.EmergencyReset();
                _lastRemote[number] = GamepadState.Neutral;
                _sync!.SetRemoteEnabled(number, action == "start");
                return;
            }
            switch (action)
            {
                case "start": slot.Safety.Start(); break;
                case "pause": slot.Safety.Pause(); break;
                case "reset": slot.Safety.Reset(); break;
                default: throw new ArgumentException("Unknown lifecycle action.");
            }
        }
    }

    public void ToggleController(int number)
    {
        lock (_routingGate)
        {
            var enabled = IsRemote(number) ? _sync!.IsRemoteEnabled(number) : Get(number).Safety.RunState == RunState.Running || ProgramLease(number) is not null;
            Lifecycle(number, enabled ? "pause" : "start");
        }
    }

    public object HandleSync(string command, JsonElement payload)
    {
        lock (_routingGate)
        {
            if (_sync is null)
            {
                if (command == "sync.stop") return new { ok = true, unavailable = true };
                throw new InvalidOperationException("LAN sync is unavailable on this host.");
            }
            if (payload.TryGetProperty("_uiSource", out var sourceElement))
            {
                var source = sourceElement.GetString() ?? throw new ArgumentException("Missing UI source.");
                if (string.IsNullOrWhiteSpace(source) || source.Length > 128
                    || !payload.TryGetProperty("_uiSequence", out var sequenceElement)
                    || !sequenceElement.TryGetInt64(out var sequence) || sequence < 0)
                    throw new ArgumentException("UI source requires a non-negative integer sequence and a non-empty source of at most 128 characters.");
                if (_syncCommandSequences.TryGetValue(source, out var latest) && sequence <= latest)
                    return new { ok = true, stale = true };
                if (!_syncCommandSequences.ContainsKey(source) && _syncCommandSequences.Count >= 1024)
                    throw new InvalidOperationException("Too many UI sessions; restart the host.");
                _syncCommandSequences[source] = sequence;
            }
            else if (payload.TryGetProperty("_uiSequence", out _))
                throw new ArgumentException("UI source and sequence must be supplied together.");
            // Management changes cannot race physical writes or the report loop.
            var previous = _slots.Keys.ToDictionary(number => number, IsRemote);
            var result = _sync.Handle(command, payload);
            foreach (var slot in _slots.Values)
                if (previous[slot.Number] != IsRemote(slot.Number))
                {
                    slot.Safety.EmergencyReset();
                    RevokeProgram(slot.Number);
                    _lastRemote[slot.Number] = GamepadState.Neutral;
                }
            return result;
        }
    }

    public ControllerRegistry(IEnumerable<ControllerSlot> slots, IXInputBackend? backend = null)
    {
        _slots = slots.ToDictionary(slot => slot.Number);
        if (_slots.Count == 0 || _slots.Keys.Any(number => number is < 1 or > 2) || _slots.Count != _slots.Keys.Distinct().Count())
        {
            throw new ArgumentException("Controller slots must contain unique numbers in the range 1..2.", nameof(slots));
        }

        _backend = backend;
    }

    public IReadOnlyList<ControllerSlot> Slots => _slots.Values.OrderBy(slot => slot.Number).ToArray();

    public ControllerSlot this[int number] => Get(number);

    public static ControllerRegistry CreateDefault(IXInputBackend backend)
    {
        var slots = Enumerable.Range(1, 2).Select(number =>
        {
            var store = new State.StateStore();
            return new ControllerSlot(number, store, new State.SafetyController(store), new Input.MappingEngine(store));
        });
        return new ControllerRegistry(slots, backend);
    }

    public ControllerSlot Get(int number)
        => _slots.TryGetValue(number, out var slot)
            ? slot
            : throw new ArgumentOutOfRangeException(nameof(number), "Controller must be 1 or 2.");

    public void SubmitAll()
    {
        lock (_routingGate)
        {
            foreach (var slot in _slots.Values)
            {
                var remote = IsRemote(slot.Number);
                var state = remote ? LanSyncAdapter.ToGamepad(_sync!.Consume(slot.Number)) : LocalState(slot.Number);
                if (remote) _lastRemote[slot.Number] = state;
                if (_backend?.IsConnected == true) _backend.Submit(slot.Number, state);
                if (!remote) _sync?.Publish(slot.Number, LanSyncAdapter.ToNetwork(state), slot.Safety.RunState == RunState.Running);
            }
        }
    }

    public void EmergencyResetAll()
    {
        lock (_routingGate)
        {
            _sync?.EmergencyStop();
            _lastRemote.Clear();
            foreach (var slot in _slots.Values) RevokeProgram(slot.Number);
            foreach (var slot in _slots.Values) slot.Safety.EmergencyReset();
        }
    }
}
