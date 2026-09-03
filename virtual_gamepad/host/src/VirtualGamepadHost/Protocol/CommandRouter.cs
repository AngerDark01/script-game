using System.Text.Json;
using VirtualGamepadHost.Input;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.Runtime;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Protocol;

public sealed class CommandRouter
{
    private readonly StateStore _store;
    private readonly SafetyController _safety;
    private readonly Func<HostStatus> _status;
    private readonly MappingEngine? _mapping;
    private readonly Func<bool> _deviceReady;

    public CommandRouter(StateStore store, SafetyController safety, Func<HostStatus> status, MappingEngine? mapping = null, Func<bool>? deviceReady = null)
    {
        _store = store;
        _safety = safety;
        _status = status;
        _mapping = mapping;
        _deviceReady = deviceReady ?? (() => true);
    }

    public string Handle(MessageEnvelope message)
    {
        try
        {
            return message.Type.Trim().ToLowerInvariant() switch
            {
                "hello" => ProtocolSerializer.Success(message.Id, new { protocol = 1, device = "xbox360" }),
                "get_status" => ProtocolSerializer.Success(message.Id, _status()),
                "start" => Start(message.Id),
                "pause" => Run(message.Id, _safety.Pause),
                "reset" => Run(message.Id, _safety.Reset),
                "emergency_reset" => Run(message.Id, _safety.EmergencyReset),
                "get_state" => ProtocolSerializer.Success(message.Id, _store.Snapshot()),
                "get_config" => GetConfig(message.Id),
                "set_config" => SetConfig(message),
                "button" => HandleButton(message),
                "set_axis" => HandleAxis(message),
                "set_trigger" => HandleTrigger(message),
                "set_state" => HandleState(message),
                "heartbeat" => HandleHeartbeat(message),
                "subscribe_state" => ProtocolSerializer.Success(message.Id, new { subscribed = true }),
                _ => ProtocolSerializer.Failure(message.Id, "unknown_type", $"Unknown message type: {message.Type}"),
            };
        }
        catch (JsonException ex)
        {
            return ProtocolSerializer.Failure(message.Id, "invalid_payload", ex.Message);
        }
        catch (ArgumentException ex)
        {
            return ProtocolSerializer.Failure(message.Id, "invalid_argument", ex.Message);
        }
    }

    private string HandleButton(MessageEnvelope message)
    {
        var payload = Deserialize<ButtonCommand>(message.Payload);
        var button = ParseButton(payload.Button);
        _store.SetButton(payload.Source, button, payload.Action.Equals("press", StringComparison.OrdinalIgnoreCase), Ttl(payload.TtlMs));
        return ProtocolSerializer.Success(message.Id, new { accepted = true });
    }

    private string HandleAxis(MessageEnvelope message)
    {
        var payload = Deserialize<AxisCommand>(message.Payload);
        _store.SetAxis(payload.Source, ParseAxis(payload.Axis), payload.Value, Ttl(payload.TtlMs));
        return ProtocolSerializer.Success(message.Id, new { accepted = true });
    }

    private string HandleTrigger(MessageEnvelope message)
    {
        var payload = Deserialize<TriggerCommand>(message.Payload);
        _store.SetTrigger(payload.Source, ParseTrigger(payload.Trigger), payload.Value, Ttl(payload.TtlMs));
        return ProtocolSerializer.Success(message.Id, new { accepted = true });
    }

    private string HandleState(MessageEnvelope message)
    {
        var payload = Deserialize<StateCommand>(message.Payload);
        _store.SetState(payload.Source, payload.State, Ttl(payload.TtlMs));
        return ProtocolSerializer.Success(message.Id, new { accepted = true });
    }

    private string HandleHeartbeat(MessageEnvelope message)
    {
        var payload = Deserialize<HeartbeatCommand>(message.Payload);
        _store.Heartbeat(payload.Source, Ttl(payload.TtlMs));
        return ProtocolSerializer.Success(message.Id, new { accepted = true });
    }

    private string GetConfig(string? id)
    {
        return _mapping is null
            ? ProtocolSerializer.Failure(id, "config_unavailable", "Mapping engine is not configured.")
            : ProtocolSerializer.Success(id, _mapping.Config);
    }

    private string SetConfig(MessageEnvelope message)
    {
        if (_mapping is null)
        {
            return ProtocolSerializer.Failure(message.Id, "config_unavailable", "Mapping engine is not configured.");
        }

        var config = MappingConfig.FromJson(message.Payload);
        _mapping.SetConfig(config);
        return ProtocolSerializer.Success(message.Id, new { accepted = true });
    }

    private static string Run(string? id, Action action)
    {
        action();
        return ProtocolSerializer.Success(id, new { accepted = true });
    }

    private string Start(string? id)
    {
        return _deviceReady()
            ? Run(id, _safety.Start)
            : ProtocolSerializer.Failure(id, "device_unavailable", "The virtual controller is not connected. Install ViGEmBus and restart the host.");
    }

    private static T Deserialize<T>(JsonElement payload)
    {
        return payload.Deserialize<T>(ProtocolSerializer.Options)
            ?? throw new JsonException($"Payload cannot be decoded as {typeof(T).Name}.");
    }

    private static TimeSpan? Ttl(int? ttlMs) => ttlMs is > 0 ? TimeSpan.FromMilliseconds(ttlMs.Value) : null;

    private static GamepadButton ParseButton(string? value) =>
        Enum.TryParse<GamepadButton>(value, true, out var button) && button != GamepadButton.None
            ? button
            : throw new ArgumentException($"Unknown button: {value}");

    private static GamepadAxis ParseAxis(string? value)
    {
        var normalized = (value ?? string.Empty).Replace("_", string.Empty).Replace("-", string.Empty).ToLowerInvariant();
        return normalized switch
        {
            "leftx" => GamepadAxis.LeftX,
            "lefty" => GamepadAxis.LeftY,
            "rightx" => GamepadAxis.RightX,
            "righty" => GamepadAxis.RightY,
            _ => throw new ArgumentException($"Unknown axis: {value}"),
        };
    }

    private static GamepadTrigger ParseTrigger(string? value) =>
        (value ?? string.Empty).ToLowerInvariant() switch
        {
            "left" or "lt" => GamepadTrigger.Left,
            "right" or "rt" => GamepadTrigger.Right,
            _ => throw new ArgumentException($"Unknown trigger: {value}"),
        };

    private sealed record ButtonCommand(string Source, string Button, string Action, int? TtlMs = null);
    private sealed record AxisCommand(string Source, string Axis, int Value, int? TtlMs = null);
    private sealed record TriggerCommand(string Source, string Trigger, int Value, int? TtlMs = null);
    private sealed record StateCommand(string Source, GamepadState State, int? TtlMs = null);
    private sealed record HeartbeatCommand(string Source, int? TtlMs = null);
}
