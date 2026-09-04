using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Runtime;

public sealed class ControllerRegistry
{
    private readonly Dictionary<int, ControllerSlot> _slots;
    private readonly IXInputBackend? _backend;

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
        if (_backend is null || !_backend.IsConnected)
        {
            return;
        }

        foreach (var slot in Slots)
        {
            _backend.Submit(slot.Number, slot.Store.Snapshot());
        }
    }

    public void EmergencyResetAll()
    {
        foreach (var slot in Slots)
        {
            slot.Safety.EmergencyReset();
        }
    }
}
