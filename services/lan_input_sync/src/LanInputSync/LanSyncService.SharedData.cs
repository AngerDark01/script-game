using System.Text.Json;

namespace LanInputSync;

public sealed partial class LanSyncService
{
    // Data sessions share identity/transport only, never controller grants.
    private const int SharePositionTtlMs = 500;
    private bool _receivePositions, _receiveEvents;
    private long _eventSequence;
    private readonly HashSet<string> _shareBlockedPeers = new();
    private sealed record PositionMessage(string actorId, string mapId, string mapVersion,
        double x, double y, double confidence, long ageMs, ulong challenge = 0);
    private sealed record PositionEntry(PositionMessage Message, long StoredAt, long AgeMs);
    private sealed record ReceivedPosition(PositionMessage Message, long ReceivedAt, Guid SessionId);
    private sealed record ReceivedEvent(string deviceId, Guid sessionId, string id, string name,
        string eventId, int eventRevision, string[] targets, long receivedAt, long deadline);
    private readonly Dictionary<string, PositionEntry> _publishedPositions = new();
    private readonly Dictionary<(string Peer, string Actor), ReceivedPosition> _sharePositions = new();
    private readonly Queue<ReceivedEvent> _sharedEvents = new();
    private readonly Queue<JsonElement> _sharedCatalogs = new();
    private sealed record DrainedSharedData(object[] Events, JsonElement[] Catalogs);

    private static PositionMessage ParsePosition(JsonElement p)
    {
        string actor = RequiredString(p, "actorId"), map = RequiredString(p, "mapId"), version = RequiredString(p, "mapVersion");
        foreach (string value in new[] { actor, map, version })
            if (value.Length is < 1 or > 64) throw new ArgumentException("Invalid position identity");
        double x = p.GetProperty("x").GetDouble(), y = p.GetProperty("y").GetDouble(), confidence = p.GetProperty("confidence").GetDouble();
        if (!p.GetProperty("ageMs").TryGetInt64(out long age)) throw new ArgumentException("Position age must be an integer");
        if (!double.IsFinite(x) || !double.IsFinite(y) || !double.IsFinite(confidence)
            || confidence is < 0 or > 1 || age is < 0 or > SharePositionTtlMs) throw new ArgumentException("Invalid or expired position");
        return new(actor, map, version, x, y, confidence, age);
    }

    private void PublishPositionLocked(JsonElement payload)
    {
        RequireMode("share");
        var position = ParsePosition(payload);
        if (payload.TryGetProperty("deadlineMs", out var expires))
        {
            long remaining = expires.GetInt64() - Environment.TickCount64;
            if (remaining <= 0) return;
            if (remaining > SharePositionTtlMs) throw new ArgumentException("Position deadline exceeds 500ms");
            position = position with { ageMs = Math.Max(position.ageMs, SharePositionTtlMs - remaining) };
        }
        if (_publishedPositions.Count >= 8 && !_publishedPositions.ContainsKey(position.actorId)) throw new InvalidOperationException("Too many position sources");
        if (JsonSerializer.SerializeToUtf8Bytes(position with { ageMs = SharePositionTtlMs, challenge = ulong.MaxValue }).Length > 512) throw new ArgumentException("Position packet too large");
        _publishedPositions[position.actorId] = new(position, Now, position.ageMs);
    }

    private void ReceivePositionLocked(Session session, byte[] payload)
    {
        if (!_receivePositions) return;
        using var doc = JsonDocument.Parse(payload);
        if (!FreshChallenge(session, doc.RootElement, out var deadline)) return;
        var p = ParsePosition(doc.RootElement);
        // Receiver-issued challenge age bounds transit/queue time without
        // comparing clocks from different PCs. Conservative double-counting
        // is preferable to extending a stale coordinate's lifetime.
        p = p with { ageMs = p.ageMs + Now - (deadline - 500) };
        if (p.ageMs > SharePositionTtlMs) return;
        var key = (session.DeviceId, p.actorId);
        if (_sharePositions.Count >= 64 && !_sharePositions.ContainsKey(key)) throw new ArgumentException("Too many remote actors");
        _sharePositions[key] = new(p, Now, session.Id);
    }

    private object[] SharedPositionsLocked()
    {
        long now = Now;
        return _sharePositions.Where(pair => pair.Value.Message.ageMs + now-pair.Value.ReceivedAt <= SharePositionTtlMs)
            .Select(pair => (object)new { deviceId = pair.Key.Peer, sessionId = pair.Value.SessionId,
                position = pair.Value.Message, ageMs = pair.Value.Message.ageMs + now-pair.Value.ReceivedAt }).ToArray();
    }

    private void PublishEventLocked(JsonElement payload)
    {
        RequireMode("share");
        long remainingMs = 500;
        if (payload.TryGetProperty("deadlineMs", out var expires))
        {
            remainingMs = expires.GetInt64() - Environment.TickCount64;
            if (remainingMs <= 0) return;
            if (remainingMs > 500) throw new ArgumentException("Event deadline exceeds 500ms");
        }
        string peer = RequiredString(payload, "deviceId");
        string name = String(payload, "name") ?? String(payload, "eventName") ?? "";
        string eventId = String(payload, "eventId") ?? "";
        int eventRevision = payload.TryGetProperty("eventRevision", out var revision) && revision.TryGetInt32(out var parsedRevision) ? parsedRevision : 0;
        if (string.IsNullOrWhiteSpace(name) && string.IsNullOrWhiteSpace(eventId)) throw new ArgumentException("Missing eventId or name");
        if (name.Length is < 1 or > 64) throw new ArgumentException("Invalid event name");
        string[] targets = payload.GetProperty("targets").EnumerateArray().Select(v => v.GetString() ?? "").ToArray();
        if (targets.Length is < 1 or > 8 || targets.Any(t => t.Length is < 1 or > 64)) throw new ArgumentException("Invalid targets");
        if (!_sessions.TryGetValue(peer, out var s) || !s.Active || !s.HasData
            || (s.Capabilities & SessionCapability.EventPublish) == 0) throw new InvalidOperationException("Event capability is not authorized");
        if (s.LastPeerChallenge == 0) throw new InvalidOperationException("共享会话正在校验，请稍后重试。");
        var message = new { type = "shared-event", id = Guid.NewGuid().ToString("N"), sequence = ++_eventSequence, name, eventId, eventRevision, targets, remainingMs, challenge = s.LastPeerChallenge };
        if (!s.Controls.Writer.TryWrite(message)) { CloseLocked(s, "event_queue_overflow"); throw new InvalidOperationException("Event queue overflow"); }
    }

    private void PublishCatalogLocked(JsonElement payload)
    {
        RequireMode("share");
        string peer = RequiredString(payload, "deviceId");
        if (!_sessions.TryGetValue(peer, out var s) || !s.Active || !s.HasData
            || (s.Capabilities & SessionCapability.CatalogPublish) == 0)
            throw new InvalidOperationException("No shared data session");
        if (s.LastPeerChallenge == 0) throw new InvalidOperationException("Shared session is still validating");
        if (!payload.TryGetProperty("catalog", out var catalog) || catalog.ValueKind != JsonValueKind.Object)
            throw new ArgumentException("Missing catalog");
        var bytes = JsonSerializer.SerializeToUtf8Bytes(catalog);
        if (bytes.Length > 6000) throw new ArgumentException("Event catalog is too large");
        var message = new { type = "shared-catalog", catalog, challenge = s.LastPeerChallenge };
        if (!s.Controls.Writer.TryWrite(message)) { CloseLocked(s, "catalog_queue_overflow"); throw new InvalidOperationException("Catalog queue overflow"); }
    }

    private void ReceiveSharedEventLocked(Session session, JsonElement message)
    {
        if (!session.Active) return;
        string type = RequiredString(message, "type");
        if (type == "shared-catalog")
        {
            if (!_receiveEvents || (session.Capabilities & SessionCapability.CatalogSubscribe) == 0) return;
            if (!FreshChallenge(session, message, out _)) return;
            if (!message.TryGetProperty("catalog", out var catalog) || catalog.ValueKind != JsonValueKind.Object) throw new InvalidDataException("Invalid catalog");
            if (_sharedCatalogs.Count >= 8) { _sharedCatalogs.Dequeue(); }
            _sharedCatalogs.Enqueue(catalog.Clone());
            return;
        }
        if (type != "shared-event") throw new InvalidDataException("Unexpected shared control message");
        if (!_receiveEvents || (session.Capabilities & SessionCapability.EventSubscribe) == 0) return;
        if (!FreshChallenge(session, message, out var deadline)) return;
        long remaining = message.TryGetProperty("remainingMs", out var remainingValue) ? remainingValue.GetInt64() : 500;
        if (remaining is <= 0 or > 500) throw new InvalidDataException("Invalid event lifetime");
        // Challenge elapsed conservatively includes sender/TLS queue and transit.
        deadline = Math.Min(deadline, deadline - 500 + remaining);
        if (Now >= deadline) return;
        long sequence = message.GetProperty("sequence").GetInt64();
        if (sequence <= session.LastSharedEvent) return;
        string id = RequiredString(message, "id"), name = RequiredString(message, "name");
        string[] targets = message.GetProperty("targets").EnumerateArray().Select(v => v.GetString() ?? "").ToArray();
        if (id.Length > 64 || name.Length is < 1 or > 64 || targets.Length is < 1 or > 8 || targets.Any(t => t.Length is < 1 or > 64))
            throw new InvalidDataException("Invalid event");
        if (_sharedEvents.Count >= 64) { CloseLocked(session, "event_inbox_overflow"); return; }
        session.LastSharedEvent = sequence;
        string eventId = message.TryGetProperty("eventId", out var eventIdValue) ? eventIdValue.GetString() ?? "" : "";
        int eventRevision = message.TryGetProperty("eventRevision", out var revisionValue) && revisionValue.TryGetInt32(out var revision) ? revision : 0;
        _sharedEvents.Enqueue(new(session.DeviceId, session.Id, id, name, eventId, eventRevision, targets, Now, deadline));
    }

    private DrainedSharedData DrainSharedEventsLocked()
    {
        var items = new List<object>();
        var catalogs = new List<JsonElement>();
        while (_sharedCatalogs.TryDequeue(out var catalog)) catalogs.Add(catalog);
        while (_sharedEvents.TryDequeue(out var e))
            if (Now <= e.deadline && _sessions.TryGetValue(e.deviceId, out var s) && s.Active && s.Id == e.sessionId)
                items.Add(new { e.deviceId, e.sessionId, e.id, e.name, e.eventId, e.eventRevision, e.targets, ageMs = Now-e.receivedAt, remainingMs = Math.Max(0, e.deadline-Now) });
        return new DrainedSharedData(items.ToArray(), catalogs.ToArray());
    }

    // Catalog synchronization has its own consumer so the workbench can keep
    // the read-only event cache current without consuming trigger messages.
    private JsonElement[] DrainSharedCatalogsLocked()
    {
        var catalogs = new List<JsonElement>();
        while (_sharedCatalogs.TryDequeue(out var catalog)) catalogs.Add(catalog);
        return catalogs.ToArray();
    }

    private static bool FreshChallenge(Session session, JsonElement message, out long deadline)
    {
        deadline = 0;
        if (!message.TryGetProperty("challenge", out var c) || !c.TryGetUInt64(out var id)
            || !session.IssuedChallenges.TryGetValue(id, out var issued)) return false;
        deadline = issued + 500;
        return Now <= deadline;
    }
}
