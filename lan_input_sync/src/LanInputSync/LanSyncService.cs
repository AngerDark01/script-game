using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text.Json;
using LiteNetLib;

namespace LanInputSync;

public sealed partial class LanSyncService : ILanSyncService
{
    internal static long Now => Stopwatch.GetTimestamp() * 1000 / Stopwatch.Frequency;
    private readonly object _gate = new();
    private readonly IdentityStore _identity;
    private readonly string[] _addresses;
    private readonly Dictionary<string, TrustedPeer> _trusted = new();
    private readonly Dictionary<string, Session> _sessions = new();
    private readonly Dictionary<string, PairRequest> _pending = new();
    private readonly Dictionary<string, Discovery> _discovered = new();
    private readonly Dictionary<string, string> _peerErrors = new();
    private readonly LocalSlot[] _local = [new(), new()];
    private readonly ReceiverSlot[] _remote = [new(), new()];
    private readonly bool[] _remoteEnabled = new bool[2];
    private readonly ConcurrentQueue<Action> _work = new();
    private readonly CancellationTokenSource _stop = new();
    private CancellationTokenSource _run = new();
    private readonly Task _worker;
    private readonly BlockingCollection<Action> _persistence = new(64);
    private readonly Task _persistenceWorker;
    private Preferences _preferences;
    private string _mode = "off";
    private string? _error;
    private string? _pairingCode;
    private DateTimeOffset _pairingExpiry;
    private NetManager? _net;
    private TcpListener? _listener;
    private int _incomingConnections;
    private long _nextBroadcast;
    private int _generation;
    private int _configurationVersion;
    private bool _networkReady;
    private bool _disposed;
    private readonly Dictionary<string, Guid> _connecting = new();
    private readonly Dictionary<string, Guid> _startVersions = new();
    private readonly Dictionary<string, Guid> _pairVersions = new();

    private sealed class LocalSlot
    {
        public PadState State = PadState.Neutral;
        public bool Enabled;
        public uint Revision;
        public uint Epoch = 1;
        public readonly Queue<Change> Changes = new();
        public bool Overflow;
        public long LastPublish;
    }
    private sealed record Change(int Slot, uint Epoch, uint Revision, bool Enabled, ushort Buttons, long Time);
    private sealed record Discovery(string DeviceId, string Name, string Address, int Port, long Seen);
    private sealed class PairRequest
    {
        public required string Id, DeviceId, Name, Fingerprint;
        public bool Incoming;
        public bool Confirmed;
        public readonly TaskCompletionSource<bool> Answer = new(TaskCreationOptions.RunContinuationsAsynchronously);
    }

    public LanSyncService(string? dataDirectory = null)
    {
        _identity = new IdentityStore(dataDirectory);
        _addresses = LocalAddresses();
        _preferences = _identity.Read<Preferences>("preferences.json") ?? new(Environment.MachineName, _addresses.FirstOrDefault() ?? "127.0.0.1", 45873, [1, 2]);
        foreach (var peer in _identity.Read<TrustedPeer[]>("trusted.json") ?? []) _trusted[peer.DeviceId] = peer;
        _persistenceWorker = Task.Factory.StartNew(() =>
        {
            foreach (var save in _persistence.GetConsumingEnumerable())
                try { save(); } catch (Exception ex) { lock (_gate) _error = "保存同步配置失败: " + ex.Message; }
        }, CancellationToken.None, TaskCreationOptions.LongRunning, TaskScheduler.Default);
        _worker = Task.Factory.StartNew(NetworkLoop, CancellationToken.None, TaskCreationOptions.LongRunning, TaskScheduler.Default);
    }

    public void Publish(int controller, PadState state, bool enabled)
    {
        if (controller is < 1 or > 2) return;
        lock (_gate)
        {
            if (_disposed || _mode != "send") return;
            var slot = _local[controller - 1];
            slot.LastPublish = Now;
            state = enabled ? state : PadState.Neutral;
            if (slot.Enabled != enabled || slot.State.Buttons != state.Buttons)
            {
                if (slot.Enabled != enabled) slot.Epoch++;
                slot.Revision++;
                if (slot.Changes.Count >= 64) { slot.Changes.Clear(); slot.Overflow = true; }
                slot.Changes.Enqueue(new(controller - 1, slot.Epoch, slot.Revision, enabled, state.Buttons, Now));
            }
            slot.Enabled = enabled; slot.State = state;
        }
    }
    public bool OwnsController(int controller)
    {
        lock (_gate) return !_disposed && _mode == "receive" && _preferences.Controllers.Contains(controller);
    }
    public bool IsRemoteEnabled(int controller)
    {
        lock (_gate) return controller is 1 or 2 && OwnsController(controller) && _remoteEnabled[controller - 1];
    }
    public bool IsRemoteActive(int controller)
    {
        lock (_gate)
        {
            WatchdogLocked();
            return IsRemoteEnabled(controller) && _remote[controller - 1].Enabled && _remote[controller - 1].LastSnapshot > 0
                && _sessions.Values.Any(s => s.Active && s.Incoming && s.Controllers.Contains(controller));
        }
    }
    public PadState Consume(int controller)
    {
        lock (_gate)
        {
            if (!IsRemoteEnabled(controller)) return PadState.Neutral;
            WatchdogLocked();
            return _remoteEnabled[controller - 1] ? _remote[controller - 1].Consume() : PadState.Neutral;
        }
    }
    public PadState Peek(int controller)
    {
        lock (_gate)
        {
            WatchdogLocked();
            return IsRemoteEnabled(controller) ? _remote[controller - 1].Output : PadState.Neutral;
        }
    }
    public void SetRemoteEnabled(int controller, bool enabled)
    {
        if (controller is < 1 or > 2) return;
        lock (_gate)
        {
            if (!OwnsController(controller)) return;
            _remote[controller - 1].Reset();
            _remoteEnabled[controller - 1] = enabled;
            foreach (var session in _sessions.Values.Where(s => s.Incoming && s.Controllers.Contains(controller)).ToArray())
            {
                session.Grants[controller - 1] = enabled ? NewGrant() : 0;
                if (!session.Controls.Writer.TryWrite(new { type = "permissions", grants = session.Grants.ToArray() })) CloseLocked(session, "control_queue_overflow");
            }
        }
    }
    public void EmergencyStop()
    {
        lock (_gate)
        {
            Array.Fill(_remoteEnabled, false);
            _sharePositions.Clear(); _sharedEvents.Clear(); _publishedPositions.Clear();
            _receivePositions = false; _receiveEvents = false;
            foreach (var slot in _remote) slot.Reset();
            foreach (var session in _sessions.Values.ToArray()) CloseLocked(session, "emergency_stop");
            foreach (var slot in _local) { slot.Changes.Clear(); slot.State = PadState.Neutral; slot.Enabled = false; slot.Epoch++; }
            _generation++;
            _startVersions.Clear();
            foreach (var peerId in _trusted.Keys) _connecting.Remove(peerId);
        }
    }

    public object Handle(string command, JsonElement payload)
    {
        try
        {
            lock (_gate)
            {
                ObjectDisposedException.ThrowIf(_disposed, this);
                switch (command)
                {
                    case "sync.share.position": PublishPositionLocked(payload); break;
                    case "sync.share.event": PublishEventLocked(payload); break;
                    case "sync.share.drain":
                        var events = DrainSharedEventsLocked();
                        return new { ok = true, events, status = StatusLocked() };
                    case "sync.status": break;
                    case "sync.configure": ConfigureLocked(payload); break;
                    case "sync.pairing":
                        if (_mode == "off") throw new InvalidOperationException("请先选择发送或接收模式。");
                        RequireNetworkReady();
                        _pairingCode = RandomNumberGenerator.GetInt32(0, 100000000).ToString("D8");
                        _pairingExpiry = DateTimeOffset.UtcNow.AddMinutes(5); break;
                    case "sync.pair":
                        RequireSenderOrShare();
                        RequireNetworkReady();
                        var address = RequiredString(payload, "address");
                        ValidateAddress(address, false);
                        var port = Int(payload, "port", 45873); ValidatePort(port);
                        var code = RequiredString(payload, "code");
                        if (code.Length != 8 || !code.All(char.IsAsciiDigit)) throw new ArgumentException("设备码应为 8 位数字。");
                        var pairGeneration = _generation; var pairToken = _run.Token;
                        ScheduleConnection("pair:" + address + ":" + port, () => PairAsync(address, port, code, pairGeneration, pairToken)); break;
                    case "sync.confirm":
                        var id = RequiredString(payload, "requestId");
                        if (!_pending.TryGetValue(id, out var request)) throw new InvalidOperationException("配对请求已失效。");
                        request.Confirmed = !payload.TryGetProperty("allow", out var a) || a.GetBoolean();
                        request.Answer.TrySetResult(request.Confirmed); break;
                    case "sync.start":
                        RequireNetworkReady();
                        var controllers = Controllers(payload, _preferences.Controllers);
                        if (_mode == "receive")
                        {
                            foreach (var c in controllers) SetRemoteEnabled(c, true);
                        }
                        else
                        {
                            RequireSenderOrShare();
                            var peerId = RequiredString(payload, "deviceId");
                            if (!_trusted.TryGetValue(peerId, out var peer)) throw new InvalidOperationException("设备尚未配对。");
                            if (_sessions.TryGetValue(peerId, out var existing)) CloseLocked(existing, "restart");
                            peer = peer with { Controllers = controllers }; _trusted[peerId] = peer; SavePreferencesLater();
                            var capturedPeer = peer; var generation = _generation; var token = _run.Token;
                            var startVersion = Guid.NewGuid();
                            bool dataOnly = _mode == "share";
                            _shareBlockedPeers.Remove(peerId);
                            ScheduleConnection(peerId, () => StartOutgoingAsync(capturedPeer, generation, startVersion, token, dataOnly));
                            _startVersions[peerId] = startVersion;
                        }
                        break;
                    case "sync.stop":
                        string? selected = String(payload, "deviceId");
                        if (_mode == "share")
                        {
                            if (selected is null) { _receivePositions = false; _receiveEvents = false; }
                            else _shareBlockedPeers.Add(selected);
                        }
                        foreach (var s in _sessions.Values.Where(s => selected is null || s.DeviceId == selected).ToArray()) CloseLocked(s, "stopped");
                        if (_mode == "receive") { Array.Fill(_remoteEnabled, false); foreach (var slot in _remote) slot.Reset(); }
                        if (selected is null) { _generation++; _startVersions.Clear(); foreach (var peerId in _trusted.Keys) _connecting.Remove(peerId); }
                        else { _startVersions.Remove(selected); _connecting.Remove(selected); }
                        break;
                    case "sync.forget":
                        var forgotten = RequiredString(payload, "deviceId");
                        if (_sessions.TryGetValue(forgotten, out var active)) CloseLocked(active, "forgotten");
                        _trusted.Remove(forgotten); _startVersions.Remove(forgotten); _pairVersions.Remove(forgotten); _connecting.Remove(forgotten);
                        foreach (var pending in _pending.Values.Where(p => p.DeviceId == forgotten)) pending.Answer.TrySetResult(false);
                        SavePreferencesLater(); break;
                    default: throw new ArgumentException("Unknown LAN sync command: " + command);
                }
                return new { ok = true, status = StatusLocked() };
            }
        }
        catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or FormatException or SocketException or KeyNotFoundException or JsonException)
        {
            lock (_gate) return new { ok = false, error = ex.Message, status = StatusLocked() };
        }
    }

    private void ConfigureLocked(JsonElement value)
    {
        string mode = String(value, "mode") ?? _mode;
        if (mode is not ("off" or "send" or "receive" or "share")) throw new ArgumentException("mode must be off, send, receive or share");
        string name = String(value, "name") ?? _preferences.Name;
        if (name.Length is < 1 or > 64) throw new ArgumentException("设备名称应为 1–64 个字符。");
        string address = String(value, "bindAddress") ?? _preferences.BindAddress;
        ValidateAddress(address, true);
        int port = Int(value, "port", _preferences.Port); ValidatePort(port);
        int rate = Int(value, "rateHz", _preferences.RateHz);
        if (rate is not (60 or 125)) throw new ArgumentException("rateHz must be 60 or 125");
        int[] controllers = Controllers(value, _preferences.Controllers);
        EmergencyStop();
        _shareBlockedPeers.Clear();
        _receivePositions = mode == "share" && value.TryGetProperty("receivePositions", out var rp) && rp.GetBoolean();
        _receiveEvents = mode == "share" && value.TryGetProperty("receiveEvents", out var re) && re.GetBoolean();
        _mode = mode; _preferences = new(name, address, port, controllers, rate); _error = null;
        _pairingCode = null;
        foreach (var p in _pending.Values) p.Answer.TrySetResult(false);
        _run.Cancel();
        _run = CancellationTokenSource.CreateLinkedTokenSource(_stop.Token);
        _networkReady = false;
        var version = ++_configurationVersion;
        _work.Enqueue(() => ConfigureNetwork(version));
        SavePreferencesLater();
    }
    private void SavePreferencesLater()
    {
        var preferences = _preferences; var trusted = _trusted.Values.ToArray();
        if (!_persistence.TryAdd(() => { _identity.Write("preferences.json", preferences); _identity.Write("trusted.json", trusted); }))
            _error = "配置保存队列繁忙，请稍后重试。";
    }
    private void ScheduleConnection(string key, Func<Task> connect)
    {
        if (_connecting.Count >= 8 || _connecting.ContainsKey(key)) throw new InvalidOperationException("连接正在进行，请稍候。");
        Guid ticket = Guid.NewGuid(); _connecting.Add(key, ticket);
        _ = Task.Run(async () =>
        {
            try { await connect(); }
            catch (Exception ex) { lock (_gate) { _error = ex.Message; _peerErrors[key] = ex.Message; } }
            finally { lock (_gate) if (_connecting.GetValueOrDefault(key) == ticket) _connecting.Remove(key); }
        });
    }
    private object StatusLocked()
    {
        WatchdogLocked();
        return new
        {
            mode = _mode, deviceId = _identity.DeviceId, name = _preferences.Name,
            receivePositions = _receivePositions, receiveEvents = _receiveEvents,
            sharedPositions = SharedPositionsLocked(), pendingSharedEvents = _sharedEvents.Count,
            bindAddress = _preferences.BindAddress, port = _preferences.Port, rateHz = _preferences.RateHz,
            networkReady = _networkReady,
            addresses = _addresses,
            pairingCode = DateTimeOffset.UtcNow < _pairingExpiry ? _pairingCode : null,
            pairingExpiresUtc = _pairingCode is null ? (DateTimeOffset?)null : _pairingExpiry,
            controllers = _preferences.Controllers, remoteEnabled = Enumerable.Range(1, 2).Where(c => _remoteEnabled[c - 1]).ToArray(),
            peers = _trusted.Values.Select(p =>
            {
                _sessions.TryGetValue(p.DeviceId, out var s);
                return new { deviceId = p.DeviceId, name = p.Name, address = p.Address, port = p.Port,
                    connected = s?.Peer?.ConnectionState == ConnectionState.Connected, syncing = s?.Active == true,
                    connecting = _connecting.ContainsKey(p.DeviceId), controllers = s?.Controllers ?? p.Controllers,
                    rttMs = s?.RttMs, error = _peerErrors.GetValueOrDefault(p.DeviceId) };
            }).ToArray(),
            discovered = _discovered.Values.Where(d => Now - d.Seen < 6000).Select(d => new { deviceId = d.DeviceId, name = d.Name, address = d.Address, port = d.Port }).ToArray(),
            pending = _pending.Values.Select(p => new { requestId = p.Id, deviceId = p.DeviceId, name = p.Name, fingerprint = p.Fingerprint, incoming = p.Incoming, confirmed = p.Confirmed }).ToArray(),
            error = _error
        };
    }

    private void WatchdogLocked()
    {
        long now = Now;
        foreach (var s in _sessions.Values.ToArray())
        {
            if (!s.Active) continue;
            string? error = null;
            if (s.Peer?.ConnectionState != ConnectionState.Connected && now - s.Created > 5000) error = "udp_connection_timeout";
            if (s.LastReceive > 0 && now - s.LastReceive > 200) error = "state_timeout";
            if (s.Challenges.TryPeek(out var challenge) && now - challenge.Time > 200) error = "health_timeout";
            if (s.Unacked.TryPeek(out var pending) && now - pending.Time > 200) error = "button_delivery_timeout";
            if (s.Incoming && s.Controllers.Any(c => _remote[c - 1].IsExpired(now, 200))) error = "input_queue_timeout";
            if (!s.Incoming && s.Controllers.Any(c => _local[c - 1].Enabled && now - _local[c - 1].LastPublish > 200)) error = "source_report_timeout";
            if (error is not null) CloseLocked(s, error);
        }
    }
    private void CloseLocked(Session s, string reason)
    {
        if (!s.Active) return;
        s.Active = false;
        if (_sessions.GetValueOrDefault(s.DeviceId) == s) _sessions.Remove(s.DeviceId);
        _peerErrors[s.DeviceId] = reason;
        foreach (var key in _sharePositions.Keys.Where(k => k.Peer == s.DeviceId).ToArray()) _sharePositions.Remove(key);
        if (s.Incoming)
            foreach (int c in s.Controllers) { _remote[c - 1].Reset(); _remoteEnabled[c - 1] = false; }
        _work.Enqueue(() => { s.Tcp.Dispose(); s.Peer?.Disconnect(); s.Crypto.Dispose(); });
    }
    private void RequireMode(string mode) { if (_mode != mode) throw new InvalidOperationException("请先切换到" + (mode == "send" ? "发送" : "接收") + "模式。"); }
    private void RequireSenderOrShare() { if (_mode is not ("send" or "share")) throw new InvalidOperationException("请先选择发送或位置与事件共享模式。"); }
    private void RequireNetworkReady() { if (!_networkReady) throw new InvalidOperationException("局域网服务正在启动或启动失败，请查看连接状态后重试。"); }
    private static string? String(JsonElement e, string key) => e.ValueKind == JsonValueKind.Object && e.TryGetProperty(key, out var value) ? value.GetString() : null;
    private static string RequiredString(JsonElement e, string key) => String(e, key) ?? throw new ArgumentException("Missing " + key);
    private static int Int(JsonElement e, string key, int fallback) => e.ValueKind == JsonValueKind.Object && e.TryGetProperty(key, out var value) ? value.GetInt32() : fallback;
    private static int[] Controllers(JsonElement e, int[] fallback)
    {
        if (e.ValueKind != JsonValueKind.Object || !e.TryGetProperty("controllers", out var values)) return fallback.ToArray();
        int[] result = values.EnumerateArray().Select(v => v.GetInt32()).Distinct().ToArray();
        if (result.Length is < 1 or > 2 || result.Any(v => v is < 1 or > 2)) throw new ArgumentException("controllers must contain 1 and/or 2");
        return result;
    }
    private static void ValidatePort(int port) { if (port is < 1024 or > 65535) throw new ArgumentException("端口应为 1024–65535。"); }
    private static bool IsPrivate(IPAddress ip)
    {
        if (ip.AddressFamily != AddressFamily.InterNetwork) return false;
        byte[] b = ip.GetAddressBytes();
        return IPAddress.IsLoopback(ip) || b[0] == 10 || (b[0] == 172 && b[1] is >= 16 and <= 31) || (b[0] == 192 && b[1] == 168) || (b[0] == 169 && b[1] == 254);
    }
    private void ValidateAddress(string address, bool local)
    {
        if (!IPAddress.TryParse(address, out var ip) || !IsPrivate(ip)) throw new ArgumentException("请选择具体的局域网 IPv4 地址。");
        if (local && !IPAddress.IsLoopback(ip) && !_addresses.Contains(address)) throw new ArgumentException("该地址不属于本机网卡。");
    }
    private static string[] LocalAddresses() => NetworkInterface.GetAllNetworkInterfaces()
        .Where(n => n.OperationalStatus == OperationalStatus.Up)
        .SelectMany(n => n.GetIPProperties().UnicastAddresses).Select(a => a.Address)
        .Where(a => IsPrivate(a) && !IPAddress.IsLoopback(a)).Select(a => a.ToString()).Distinct().Append("127.0.0.1").ToArray();
    public void Dispose()
    {
        lock (_gate)
        {
            if (_disposed) return;
            EmergencyStop(); _disposed = true; _mode = "off";
            _configurationVersion++; _networkReady = false;
            foreach (var p in _pending.Values) p.Answer.TrySetResult(false);
            _run.Cancel(); _stop.Cancel(); _listener?.Stop();
        }
        _worker.Wait(TimeSpan.FromSeconds(3));
        _persistence.CompleteAdding(); _persistenceWorker.Wait(TimeSpan.FromSeconds(3));
        _identity.Dispose();
    }
}
