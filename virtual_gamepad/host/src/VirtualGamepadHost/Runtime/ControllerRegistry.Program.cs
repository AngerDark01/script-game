using System.Text.Json;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.Protocol;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Runtime;

public sealed partial class ControllerRegistry
{
    // Separate output lease: never starts Safety/Mapping or captures physical keys.
    // A pause/F7/F8/F9 revokes the token; stale writes cannot reacquire implicitly.
    private sealed class ProgramOutputLease
    {
        public string Token = Guid.NewGuid().ToString("N");
        public StateStore Store = new();
        public long Deadline = Environment.TickCount64 + 1000;
        public long OutputDeadline;
    }
    private readonly Dictionary<int, ProgramOutputLease> _programLeases = new();

    private ProgramOutputLease? ProgramLease(int number)
    {
        if (!_programLeases.TryGetValue(number, out var lease)) return null;
        if (Environment.TickCount64 < lease.Deadline) return lease;
        _programLeases.Remove(number);
        return null;
    }

    private GamepadState LocalState(int number)
    {
        var lease = ProgramLease(number);
        return lease is null ? Get(number).Store.Snapshot()
            : Environment.TickCount64 < lease.OutputDeadline ? lease.Store.Snapshot() : GamepadState.Neutral;
    }

    public bool IsProgram(int number)
    {
        lock (_routingGate) return ProgramLease(number) is not null;
    }

    public object HandleProgram(string command, JsonElement payload)
    {
        lock (_routingGate)
        {
            int number = payload.GetProperty("controller").GetInt32();
            var slot = Get(number);
            if (IsRemote(number)) throw new RemoteOwnershipException(number);
            var lease = ProgramLease(number);
            if (command == "program.acquire")
            {
                if (slot.Safety.RunState != RunState.Paused || lease is not null)
                    throw new InvalidOperationException("Pause the controller and release its program session first.");
                slot.Safety.Pause();
                lease = new ProgramOutputLease();
                _programLeases[number] = lease;
                return new { token = lease.Token, controller = number };
            }
            if (lease is null || payload.GetProperty("token").GetString() != lease.Token)
                throw new InvalidOperationException("Program session expired or was revoked. Explicit start is required.");
            if (command == "program.release")
            {
                _programLeases.Remove(number);
                return new { accepted = true };
            }
            if (command != "program.state") throw new ArgumentException("Unknown program command.");
            int ttl = payload.GetProperty("ttlMs").GetInt32();
            if (ttl is < 1 or > 300) throw new ArgumentException("Program output TTL must be 1..300ms.");
            var state = payload.GetProperty("state").Deserialize<GamepadState>(ProtocolSerializer.Options)
                ?? throw new ArgumentException("Program state is required.");
            lease.Store.SetState("program", state, TimeSpan.FromMilliseconds(ttl));
            lease.OutputDeadline = Environment.TickCount64 + ttl;
            lease.Deadline = Environment.TickCount64 + 1000;
            return new { accepted = true };
        }
    }
}
