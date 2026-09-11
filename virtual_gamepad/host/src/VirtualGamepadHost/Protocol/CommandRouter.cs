using System.Text.Json;
using VirtualGamepadHost.Input;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.Runtime;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Protocol;

public sealed class CommandRouter
{
    private readonly ControllerRegistry _registry;
    private readonly Func<HostStatus> _status;
    private readonly Func<bool> _deviceReady;
    private readonly object _lifecycleGate = new();
    private readonly Dictionary<(int Controller, string Source), long> _latestLifecycleSequences = new();

    public CommandRouter(ControllerRegistry registry, Func<HostStatus> status, Func<bool>? deviceReady = null)
    {
        _registry = registry;
        _status = status;
        _deviceReady = deviceReady ?? (() => true);
    }

    public CommandRouter(StateStore store, SafetyController safety, Func<HostStatus> status, MappingEngine? mapping = null, Func<bool>? deviceReady = null)
    {
        _registry = new ControllerRegistry(new[] { new ControllerSlot(1, store, safety, mapping ?? new MappingEngine(store)) });
        _status = status;
        _deviceReady = deviceReady ?? (() => true);
    }

    public string Handle(MessageEnvelope message)
    {
        try
        {
            if (message.Type.StartsWith("program.", StringComparison.Ordinal))
            {
                if (message.Type == "program.acquire" && !_deviceReady())
                    return ProtocolSerializer.Failure(message.Id, "device_unavailable", "Virtual controller is not connected.");
                return ProtocolSerializer.Success(message.Id, _registry.HandleProgram(message.Type, message.Payload));
            }
            if (message.Type.StartsWith("sync.", StringComparison.Ordinal))
            {
                var result = _registry.HandleSync(message.Type, message.Payload);
                var json = JsonSerializer.SerializeToElement(result, ProtocolSerializer.Options);
                if (json.TryGetProperty("ok", out var ok) && ok.ValueKind == JsonValueKind.False)
                    return ProtocolSerializer.Failure(message.Id, "sync_error", json.GetProperty("error").GetString() ?? "Sync command failed.");
                return ProtocolSerializer.Success(message.Id, result);
            }
            return message.Type.Trim().ToLowerInvariant() switch
            {
                "hello" => ProtocolSerializer.Success(message.Id, new { protocol = 1, device = "xbox360", controllers = _registry.Slots.Count }),
                "get_status" => ProtocolSerializer.Success(message.Id, _status()),
                "start" => Start(message),
                "pause" => Lifecycle(message, slot => _registry.Lifecycle(slot.Number, "pause")),
                "reset" => Lifecycle(message, slot => _registry.Lifecycle(slot.Number, "reset")),
                "emergency_reset" => Run(message.Id, _registry.EmergencyResetAll),
                "get_state" => ProtocolSerializer.Success(message.Id, _registry.EffectiveState(Slot(message).Number)),
                "get_config" => GetConfig(message),
                "set_config" => SetConfig(message),
                "button" => HandleButton(message),
                "set_axis" => HandleAxis(message),
                "set_trigger" => HandleTrigger(message),
                "set_state" => HandleState(message),
                "event.state" => HandleEventState(message),
                "event.clear" => HandleEventClear(message),
                "heartbeat" => HandleHeartbeat(message),
                "subscribe_state" => ProtocolSerializer.Success(message.Id, new { subscribed = true }),
                _ => ProtocolSerializer.Failure(message.Id, "unknown_type", $"Unknown message type: {message.Type}"),
            };
        }
        catch (JsonException ex)
        {
            return ProtocolSerializer.Failure(message.Id, "invalid_payload", ex.Message);
        }
        catch (KeyNotFoundException ex)
        {
            return ProtocolSerializer.Failure(message.Id, "invalid_payload", ex.Message);
        }
        catch (ArgumentException ex)
        {
            return ProtocolSerializer.Failure(message.Id, "invalid_argument", ex.Message);
        }
        catch (RemoteOwnershipException ex)
        {
            return ProtocolSerializer.Failure(message.Id, "slot_owned_by_remote", ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return ProtocolSerializer.Failure(message.Id, "invalid_argument", ex.Message);
        }
        catch (FormatException ex)
        {
            return ProtocolSerializer.Failure(message.Id, "invalid_argument", ex.Message);
        }
    }

    private ControllerSlot Slot(MessageEnvelope message)
    {
        var controller = message.Payload.TryGetProperty("controller", out var value) && value.ValueKind != JsonValueKind.Null ? value.GetInt32() : 1;
        return _registry.Get(controller);
    }

    private string Start(MessageEnvelope message)
    {
        if (!_deviceReady())
        {
            return ProtocolSerializer.Failure(message.Id, "device_unavailable", "The virtual controller is not connected. Install ViGEmBus and restart the host.");
        }

        return Lifecycle(message, slot => _registry.Lifecycle(slot.Number, "start"));
    }

    private string Lifecycle(MessageEnvelope message, Action<ControllerSlot> action)
    {
        var slot = Slot(message);
        lock (_lifecycleGate)
        {
            // The sequence check and the safety mutation form one ordering
            // fence.  Releasing this lock between them would allow an older
            // Start that already passed validation to run after a newer Pause.
            if (!AcceptLifecycleSequence(slot.Number, message.Payload))
            {
                return ProtocolSerializer.Success(message.Id, new { accepted = false, stale = true, controller = slot.Number });
            }

            action(slot);
        }
        return ProtocolSerializer.Success(message.Id, new { accepted = true, controller = slot.Number });
    }

    private bool AcceptLifecycleSequence(int controller, JsonElement payload)
    {
        var hasSource = payload.TryGetProperty("source", out var sourceElement) && sourceElement.ValueKind != JsonValueKind.Null;
        var hasSequence = payload.TryGetProperty("sequence", out var sequenceElement) && sequenceElement.ValueKind != JsonValueKind.Null;
        if (!hasSource && !hasSequence)
        {
            // Existing F7/F8 and older pipe clients are deliberately unfenced.
            return true;
        }
        if (!hasSource || !hasSequence)
        {
            throw new ArgumentException("Lifecycle source and sequence must be supplied together.");
        }

        var source = sourceElement.GetString();
        if (string.IsNullOrWhiteSpace(source))
        {
            throw new ArgumentException("Lifecycle source must be non-empty.");
        }
        var sequence = sequenceElement.GetInt64();
        if (sequence < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(sequence), "Lifecycle sequence must be non-negative.");
        }

        var key = (controller, source);
        if (_latestLifecycleSequences.TryGetValue(key, out var latest) && sequence <= latest)
        {
            return false;
        }
        _latestLifecycleSequences[key] = sequence;
        return true;
    }

    private string HandleButton(MessageEnvelope message)
    {
        var payload = Deserialize<ButtonCommand>(message.Payload);
        var slot = _registry.Get(payload.Controller ?? 1);
        _registry.ExecuteLocal(slot.Number, local => local.Store.SetButton(payload.Source, ParseButton(payload.Button), payload.Action.Equals("press", StringComparison.OrdinalIgnoreCase), Ttl(payload.TtlMs)));
        return ProtocolSerializer.Success(message.Id, new { accepted = true, controller = slot.Number });
    }

    private string HandleAxis(MessageEnvelope message)
    {
        var payload = Deserialize<AxisCommand>(message.Payload);
        var slot = _registry.Get(payload.Controller ?? 1);
        _registry.ExecuteLocal(slot.Number, local => local.Store.SetAxis(payload.Source, ParseAxis(payload.Axis), payload.Value, Ttl(payload.TtlMs)));
        return ProtocolSerializer.Success(message.Id, new { accepted = true, controller = slot.Number });
    }

    private string HandleTrigger(MessageEnvelope message)
    {
        var payload = Deserialize<TriggerCommand>(message.Payload);
        var slot = _registry.Get(payload.Controller ?? 1);
        _registry.ExecuteLocal(slot.Number, local => local.Store.SetTrigger(payload.Source, ParseTrigger(payload.Trigger), payload.Value, Ttl(payload.TtlMs)));
        return ProtocolSerializer.Success(message.Id, new { accepted = true, controller = slot.Number });
    }

    private string HandleState(MessageEnvelope message)
    {
        var payload = Deserialize<StateCommand>(message.Payload);
        var slot = _registry.Get(payload.Controller ?? 1);
        _registry.ExecuteLocal(slot.Number, local => local.Store.SetState(payload.Source, payload.State, Ttl(payload.TtlMs)));
        return ProtocolSerializer.Success(message.Id, new { accepted = true, controller = slot.Number });
    }

    private string HandleEventState(MessageEnvelope message)
    {
        var payload = Deserialize<StateCommand>(message.Payload);
        var slot = _registry.Get(payload.Controller ?? 1);
        HostDiagnostics.Write($"event.state received controller={slot.Number} source={payload.Source} buttons={payload.State.Buttons} axes={payload.State.LeftStickX},{payload.State.LeftStickY}");
        _registry.SetEventState(slot.Number, payload.Source, payload.State, Ttl(payload.TtlMs));
        return ProtocolSerializer.Success(message.Id, new { accepted = true, controller = slot.Number, mode = "event" });
    }

    private string HandleEventClear(MessageEnvelope message)
    {
        var controller = message.Payload.TryGetProperty("controller", out var value) && value.ValueKind != JsonValueKind.Null ? value.GetInt32() : 1;
        var source = message.Payload.TryGetProperty("source", out var sourceElement) ? sourceElement.GetString() : null;
        _registry.ClearEventState(controller, source);
        return ProtocolSerializer.Success(message.Id, new { accepted = true, controller, mode = "event" });
    }

    private string HandleHeartbeat(MessageEnvelope message)
    {
        var payload = Deserialize<HeartbeatCommand>(message.Payload);
        var slot = _registry.Get(payload.Controller ?? 1);
        _registry.ExecuteLocal(slot.Number, local => local.Store.Heartbeat(payload.Source, Ttl(payload.TtlMs)));
        return ProtocolSerializer.Success(message.Id, new { accepted = true, controller = slot.Number });
    }

    private static string Run(string? id, Action action)
    {
        action();
        return ProtocolSerializer.Success(id, new { accepted = true });
    }

    private string GetConfig(MessageEnvelope message)
    {
        var slot = Slot(message);
        var config = slot.Mapping.Config;
        return ProtocolSerializer.Success(message.Id, new { controller = slot.Number, bindings = config.Bindings, startPause = config.StartPause, emergencyReset = config.EmergencyReset });
    }

    private string SetConfig(MessageEnvelope message)
    {
        var slot = Slot(message);
        slot.Mapping.SetConfig(MappingConfig.FromJson(message.Payload));
        return ProtocolSerializer.Success(message.Id, new { accepted = true, controller = slot.Number });
    }

    private static T Deserialize<T>(JsonElement payload)
        => payload.Deserialize<T>(ProtocolSerializer.Options) ?? throw new JsonException($"Payload cannot be decoded as {typeof(T).Name}.");

    private static TimeSpan? Ttl(int? ttlMs) => ttlMs is > 0 ? TimeSpan.FromMilliseconds(ttlMs.Value) : null;

    private static GamepadButton ParseButton(string? value) => Enum.TryParse<GamepadButton>(value, true, out var button) && button != GamepadButton.None ? button : throw new ArgumentException($"Unknown button: {value}");

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

    private static GamepadTrigger ParseTrigger(string? value) => (value ?? string.Empty).ToLowerInvariant() switch
    {
        "left" or "lt" => GamepadTrigger.Left,
        "right" or "rt" => GamepadTrigger.Right,
        _ => throw new ArgumentException($"Unknown trigger: {value}"),
    };

    private sealed record ButtonCommand(string Source, string Button, string Action, int? TtlMs = null, int? Controller = null);
    private sealed record AxisCommand(string Source, string Axis, int Value, int? TtlMs = null, int? Controller = null);
    private sealed record TriggerCommand(string Source, string Trigger, int Value, int? TtlMs = null, int? Controller = null);
    private sealed record StateCommand(string Source, GamepadState State, int? TtlMs = null, int? Controller = null);
    private sealed record HeartbeatCommand(string Source, int? TtlMs = null, int? Controller = null);
}
