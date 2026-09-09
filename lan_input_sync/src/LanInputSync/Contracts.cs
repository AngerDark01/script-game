using System.Text.Json;

namespace LanInputSync;

public sealed record PadState(ushort Buttons = 0, byte LeftTrigger = 0, byte RightTrigger = 0,
    short LeftStickX = 0, short LeftStickY = 0, short RightStickX = 0, short RightStickY = 0)
{
    public static PadState Neutral { get; } = new();
}

/// <summary>Host-facing boundary. No driver, UI, keyboard capture or host assembly dependencies.</summary>
public interface ILanSyncService : IDisposable
{
    // Called once per local output report. Must never block on I/O.
    void Publish(int controller, PadState state, bool enabled);
    // True for slots reserved by receiver mode, even when its output is paused.
    bool OwnsController(int controller);
    // Called exactly once per output report; consumes at most one ordered button transition.
    PadState Consume(int controller);
    bool IsRemoteEnabled(int controller);
    // Permission can be ready while no sender is actively producing reports.
    bool IsRemoteActive(int controller) => IsRemoteEnabled(controller);
    void SetRemoteEnabled(int controller, bool enabled);
    // Revokes remote authorization and stops sending; pending packets cannot restart output.
    void EmergencyStop();
    // Local-only management entry. Long operations are scheduled, result/status is JSON serializable.
    object Handle(string command, JsonElement payload);
}
