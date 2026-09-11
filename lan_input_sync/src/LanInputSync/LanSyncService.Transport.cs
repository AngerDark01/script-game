using System.Buffers.Binary;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using LiteNetLib;

namespace LanInputSync;

public sealed partial class LanSyncService
{
    // Internal deterministic fault seams; never exposed over management or network APIs.
    internal Func<byte, bool>? SuppressDatagramForTest { get; set; }
    internal Action? BeforePollForTest { get; set; }
    private void ConfigureNetwork(int version)
    {
        Preferences preferences; string mode; CancellationToken token;
        lock (_gate)
        {
            if (version != _configurationVersion || _disposed) return;
            token = _run.Token; mode = _mode; preferences = _preferences;
        }
        _listener?.Stop(); _listener = null;
        _net?.Stop(); _net = null;
        if (mode == "off") return;
        var listener = new EventBasedNetListener();
        var manager = new NetManager(listener)
        {
            IPv6Enabled = false, BroadcastReceiveEnabled = true, UnconnectedMessagesEnabled = true,
            UpdateTime = 1, DisconnectTimeout = 1000, ChannelsCount = 4, AutoRecycle = true,
            EnableStatistics = true
        };
        listener.ConnectionRequestEvent += request =>
        {
            try
            {
                if (request.Data.AvailableBytes > 128) { request.Reject(); return; }
                string key = request.Data.GetString();
                Session? session;
                lock (_gate)
                {
                    session = _sessions.Values.FirstOrDefault(s => s.Active && s.Incoming && s.Peer is null && s.Token == key && s.Address == request.RemoteEndPoint.Address.ToString());
                }
                if (session is null) { request.Reject(); return; }
                var peer = request.Accept();
                bool keep;
                lock (_gate) { keep = session.Active; if (keep) session.Peer = peer; }
                if (!keep) peer.Disconnect();
            }
            catch { request.Reject(); }
        };
        listener.NetworkReceiveEvent += (peer, reader, channel, method) =>
        {
            if (reader.AvailableBytes > 554) return;
            Session? session;
            lock (_gate) session = _sessions.Values.FirstOrDefault(s => s.Active && s.Peer == peer);
            if (session is null) return;
            byte[] bytes = reader.GetRemainingBytes();
            if (!session.Crypto.TryDecode(bytes, out byte lane, out var payload) || lane != channel) return;
            try { ReceivePacket(session, lane, payload); }
            catch (Exception ex) when (ex is InvalidDataException or ArgumentException or EndOfStreamException or OverflowException or JsonException or KeyNotFoundException or InvalidOperationException or FormatException)
            { lock (_gate) CloseLocked(session, "invalid_packet"); }
        };
        listener.PeerDisconnectedEvent += (peer, info) =>
        {
            lock (_gate)
            {
                var session = _sessions.Values.FirstOrDefault(s => s.Peer == peer);
                if (session is not null) CloseLocked(session, "udp_disconnected");
            }
        };
        listener.NetworkReceiveUnconnectedEvent += (endpoint, reader, type) =>
        {
            if (reader.AvailableBytes > 512 || !IsPrivate(endpoint.Address)) return;
            try
            {
                using var document = JsonDocument.Parse(reader.GetRemainingBytes());
                var d = document.RootElement;
                if (String(d, "protocol") != "automodules.lan-input/1") return;
                string id = RequiredString(d, "deviceId"), name = RequiredString(d, "name");
                if (id == _identity.DeviceId || id.Length != 64 || !id.All(Uri.IsHexDigit)) return;
                ValidateName(name); int port = Int(d, "port", 0); ValidatePort(port);
                lock (_gate)
                {
                    if (_discovered.Count >= 64 && !_discovered.ContainsKey(id)) return;
                    _discovered[id] = new(id, name, endpoint.Address.ToString(), port, Now);
                }
            }
            catch (Exception ex) when (ex is JsonException or ArgumentException or InvalidOperationException or InvalidDataException) { }
        };
        if (!manager.Start(IPAddress.Parse(preferences.BindAddress), IPAddress.IPv6None, preferences.Port)) throw new IOException("无法绑定局域网 UDP 端口，可能已被其他进程占用。");
        try
        {
            var tcp = new TcpListener(IPAddress.Parse(preferences.BindAddress), preferences.Port);
            tcp.Start(16);
            bool stale;
            lock (_gate)
            {
                stale = version != _configurationVersion || _disposed;
                if (!stale) { _listener = tcp; _net = manager; _networkReady = true; }
            }
            if (stale) { tcp.Stop(); manager.Stop(); return; }
            _ = AcceptLoopAsync(tcp, token);
        }
        catch { manager.Stop(); throw; }
        _nextBroadcast = 0;
    }

    private void NetworkLoop()
    {
        try
        {
            while (!_stop.IsCancellationRequested)
            {
                try
                {
                    for (int n = 0; n < 64 && _work.TryDequeue(out var work); n++) work();
                    BeforePollForTest?.Invoke();
                    _net?.PollEvents();
                    var sends = CollectPackets();
                    foreach (var (session, lane, payload) in sends)
                    {
                        if (!session.Active || session.Peer?.ConnectionState != ConnectionState.Connected) continue;
                        byte[] encrypted = session.Crypto.Encode(lane, payload);
                        if (SuppressDatagramForTest?.Invoke(lane) == true) continue;
                        session.Peer.Send(encrypted, lane, lane == 1 ? DeliveryMethod.ReliableOrdered : DeliveryMethod.Sequenced);
                    }
                    Broadcast();
                }
                catch (Exception ex) when (ex is not OutOfMemoryException)
                {
                    lock (_gate)
                    {
                        _error = "局域网服务: " + ex.Message;
                        foreach (var s in _sessions.Values.ToArray()) CloseLocked(s, "network_error");
                    }
                }
                Thread.Sleep(1);
            }
        }
        finally
        {
            _listener?.Stop(); _net?.Stop();
            while (_work.TryDequeue(out var work)) { try { work(); } catch { } }
        }
    }

    private List<(Session Session, byte Lane, byte[] Payload)> CollectPackets()
    {
        var packets = new List<(Session, byte, byte[])>();
        lock (_gate)
        {
            WatchdogLocked();
            long now = Now;
            Change[] changes = _local.SelectMany(s => s.Changes).ToArray();
            bool overflow = _local.Any(s => s.Overflow);
            foreach (var slot in _local) { slot.Changes.Clear(); slot.Overflow = false; }
            foreach (var s in _sessions.Values.ToArray())
            {
                if (!s.Active || s.Peer?.ConnectionState != ConnectionState.Connected) continue;
                if (s.LastReceive == 0) s.LastReceive = now;
                if (overflow && !s.Incoming && !s.DataOnly) { CloseLocked(s, "publication_queue_overflow"); continue; }
                if (now - s.LastProbe >= 50)
                {
                    s.LastProbe = now;
                    ulong id = ++s.ChallengeId;
                    s.Challenges.Enqueue((id, now));
                    if (s.DataOnly)
                    {
                        s.IssuedChallenges[id] = now;
                        foreach (var old in s.IssuedChallenges.Where(p => now-p.Value > 500).Select(p => p.Key).ToArray()) s.IssuedChallenges.Remove(old);
                    }
                    byte[] probe = new byte[9]; probe[0] = 0; BinaryPrimitives.WriteUInt64LittleEndian(probe.AsSpan(1), id);
                    packets.Add((s, 2, probe));
                }
                if (s.DataOnly)
                {
                    if (now - s.LastSend >= 33)
                    {
                        s.LastSend = now;
                        foreach (var p in _publishedPositions.Values)
                        {
                            long age = p.AgeMs + now - p.StoredAt;
                            if (age <= SharePositionTtlMs && s.LastPeerChallenge > 0)
                                packets.Add((s, 0, JsonSerializer.SerializeToUtf8Bytes(p.Message with { ageMs = age, challenge = s.LastPeerChallenge })));
                        }
                    }
                    continue;
                }
                if (s.Incoming) continue;
                foreach (int controller in s.Controllers)
                {
                    int i = controller - 1;
                    if (s.Grants[i] == 0) continue;
                    var local = _local[i];
                    if (!s.Initialized[i])
                    {
                        if (s.Unacked.Count >= 64) { CloseLocked(s, "button_queue_overflow"); break; }
                        packets.Add((s, 1, EncodeChange(new(i, local.Epoch, local.Revision, local.Enabled, local.State.Buttons, now), s.Grants[i], true)));
                        s.SentRevision[i] = local.Revision; s.Initialized[i] = true;
                        s.Unacked.Enqueue((i, local.Revision, now));
                    }
                    foreach (var change in changes.Where(c => c.Slot == i && c.Revision > s.SentRevision[i]))
                    {
                        if (now - change.Time > 200 || s.Unacked.Count >= 64) { CloseLocked(s, "button_queue_overflow"); break; }
                        packets.Add((s, 1, EncodeChange(change, s.Grants[i], false)));
                        s.SentRevision[i] = change.Revision;
                        s.Unacked.Enqueue((i, change.Revision, now));
                    }
                }
                if (now - s.LastSend >= 1000d / _preferences.RateHz)
                {
                    s.LastSend = now;
                    using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
                    writer.Write((byte)s.Controllers.Length);
                    foreach (int c in s.Controllers)
                    {
                        int i = c - 1; var slot = _local[i];
                        writer.Write((byte)i); writer.Write(s.Grants[i]); writer.Write(slot.Epoch); writer.Write(slot.Revision); writer.Write(slot.Enabled);
                        WritePad(writer, slot.State);
                    }
                    packets.Add((s, 0, stream.ToArray()));
                }
            }
        }
        return packets;
    }

    private static byte[] EncodeChange(Change change, uint grant, bool baseline)
    {
        using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
        writer.Write((byte)change.Slot); writer.Write(grant); writer.Write(change.Epoch); writer.Write(change.Revision);
        writer.Write(change.Enabled); writer.Write(change.Buttons); writer.Write(baseline);
        return stream.ToArray();
    }
    private void ReceivePacket(Session session, byte lane, byte[] payload)
    {
        byte[]? reply = null;
        lock (_gate)
        {
            if (!session.Active) return;
            if (session.DataOnly && lane == 0)
            {
                ReceivePositionLocked(session, payload);
                return;
            }
            if (session.DataOnly && lane == 1) throw new InvalidDataException("Input packets forbidden in data session");
            using var stream = new MemoryStream(payload); using var reader = new BinaryReader(stream);
            long now = Now;
            if (lane == 0)
            {
                if (!session.Incoming) throw new InvalidDataException();
                int count = reader.ReadByte(); if (count is < 1 or > 2) throw new InvalidDataException();
                HashSet<int> seen = [];
                for (int n = 0; n < count; n++)
                {
                    int i = reader.ReadByte(); uint grant = reader.ReadUInt32(), epoch = reader.ReadUInt32(), revision = reader.ReadUInt32();
                    bool enabled = reader.ReadBoolean(); PadState state = ReadPad(reader);
                    if (i > 1 || !session.Controllers.Contains(i + 1) || !seen.Add(i)) throw new InvalidDataException();
                    if (_remoteEnabled[i] && grant == session.Grants[i] && grant != 0) _remote[i].Snapshot(epoch, revision, enabled, state, now);
                }
                session.LastReceive = now;
            }
            else if (lane == 1)
            {
                if (!session.Incoming) throw new InvalidDataException();
                int i = reader.ReadByte(); uint grant = reader.ReadUInt32(), epoch = reader.ReadUInt32(), revision = reader.ReadUInt32();
                bool enabled = reader.ReadBoolean(); ushort buttons = reader.ReadUInt16(); bool baseline = reader.ReadBoolean();
                if (i > 1 || !session.Controllers.Contains(i + 1)) throw new InvalidDataException();
                if (_remoteEnabled[i] && grant != 0 && session.Grants[i] == grant)
                {
                    if (baseline) _remote[i].Reset();
                    if (!_remote[i].Transition(epoch, revision, enabled, buttons, now)) CloseLocked(session, "button_revision_gap_or_overflow");
                }
                session.ReceivedRevision[i] = Math.Max(session.ReceivedRevision[i], revision);
                // Ack received transitions, even for a locally paused route. Output queue has its own deadline.
                using var ack = new MemoryStream(); using var writer = new BinaryWriter(ack);
                writer.Write((byte)2); writer.Write((byte)i); writer.Write(revision);
                reply = ack.ToArray();
            }
            else if (lane == 2 || lane == 3)
            {
                byte kind = reader.ReadByte();
                if (kind == 0)
                {
                    ulong challenge = reader.ReadUInt64();
                    session.LastPeerChallenge = challenge;
                    reply = new byte[17]; reply[0] = 1; BinaryPrimitives.WriteUInt64LittleEndian(reply.AsSpan(1), challenge);
                    BinaryPrimitives.WriteUInt32LittleEndian(reply.AsSpan(9), session.ReceivedRevision[0]);
                    BinaryPrimitives.WriteUInt32LittleEndian(reply.AsSpan(13), session.ReceivedRevision[1]);
                }
                else if (kind == 1)
                {
                    ulong challenge = reader.ReadUInt64();
                    while (session.Challenges.TryPeek(out var next) && next.Id <= challenge)
                    {
                        session.Challenges.Dequeue();
                        if (next.Id == challenge) session.RttMs = now - next.Time;
                    }
                    if (!session.Incoming || session.DataOnly) session.LastReceive = now;
                    uint revision0 = reader.ReadUInt32(), revision1 = reader.ReadUInt32();
                    var retained = session.Unacked.Where(a => a.Revision > (a.Slot == 0 ? revision0 : revision1)).ToArray();
                    session.Unacked.Clear(); foreach (var a in retained) session.Unacked.Enqueue(a);
                }
                else if (kind == 2)
                {
                    int i = reader.ReadByte(); uint revision = reader.ReadUInt32();
                    if (i > 1) throw new InvalidDataException();
                    var keep = session.Unacked.Where(a => a.Slot != i || a.Revision > revision).ToArray();
                    session.Unacked.Clear(); foreach (var a in keep) session.Unacked.Enqueue(a);
                }
                else throw new InvalidDataException();
            }
            if (stream.Position != stream.Length) throw new InvalidDataException("Trailing bytes");
        }
        if (reply is not null && session.Active && SuppressDatagramForTest?.Invoke(3) != true)
            session.Peer?.Send(session.Crypto.Encode(3, reply), 3, DeliveryMethod.Sequenced);
    }
    private static void WritePad(BinaryWriter writer, PadState state)
    {
        writer.Write(state.Buttons); writer.Write(state.LeftTrigger); writer.Write(state.RightTrigger);
        writer.Write(state.LeftStickX); writer.Write(state.LeftStickY); writer.Write(state.RightStickX); writer.Write(state.RightStickY);
    }
    private static PadState ReadPad(BinaryReader reader) => new(reader.ReadUInt16(), reader.ReadByte(), reader.ReadByte(), reader.ReadInt16(), reader.ReadInt16(), reader.ReadInt16(), reader.ReadInt16());

    private void Broadcast()
    {
        if (_net is null || Now < _nextBroadcast) return;
        _nextBroadcast = Now + 1500;
        byte[] bytes; int port;
        lock (_gate)
        {
            if (_mode == "off") return;
            foreach (var item in _discovered.Where(p => Now - p.Value.Seen > 6000).Select(p => p.Key).ToArray()) _discovered.Remove(item);
            bytes = JsonSerializer.SerializeToUtf8Bytes(new { protocol = "automodules.lan-input/1", deviceId = _identity.DeviceId, name = _preferences.Name, port = _preferences.Port });
            port = _preferences.Port;
        }
        _net.SendBroadcast(bytes, port);
    }
}
