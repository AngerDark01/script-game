using System.Buffers.Binary;
using System.Net;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Authentication;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.Json;
using System.Threading.Channels;
using LiteNetLib;

namespace LanInputSync;

public sealed partial class LanSyncService
{
    internal Action<string>? BeforeSessionRegistrationForTest { get; set; }
    private sealed class Session
    {
        public required string DeviceId, Name, Address, Token;
        public required int[] Controllers;
        public required Guid Id;
        public required SecurePackets Crypto;
        public required TcpClient Tcp;
        public required SslStream Tls;
        public bool Incoming;
        public bool DataOnly;
        public long LastSharedEvent;
        public ulong LastPeerChallenge;
        public readonly Dictionary<ulong, long> IssuedChallenges = new();
        public bool Active = true;
        public NetPeer? Peer;
        public long Created = Now, LastReceive, LastSend, LastProbe;
        public double? RttMs;
        public ulong ChallengeId;
        public readonly Queue<(ulong Id, long Time)> Challenges = new();
        public readonly Queue<(int Slot, uint Revision, long Time)> Unacked = new();
        public readonly uint[] SentRevision = new uint[2];
        public readonly bool[] Initialized = new bool[2];
        public readonly uint[] Grants = new uint[2];
        public readonly uint[] ReceivedRevision = new uint[2];
        public readonly Channel<object> Controls = Channel.CreateBounded<object>(new BoundedChannelOptions(16) { FullMode = BoundedChannelFullMode.Wait, SingleReader = true });
    }

    private async Task AcceptLoopAsync(TcpListener listener, CancellationToken token)
    {
        try
        {
            while (!token.IsCancellationRequested)
            {
                var tcp = await listener.AcceptTcpClientAsync(token);
                if (Interlocked.Increment(ref _incomingConnections) > 16)
                { Interlocked.Decrement(ref _incomingConnections); tcp.Dispose(); continue; }
                _ = Task.Run(async () =>
                {
                    try { await AcceptClientAsync(tcp, token); }
                    catch (Exception ex) when (ex is not OutOfMemoryException)
                    { lock (_gate) if (!token.IsCancellationRequested) _error = "连接失败: " + ex.Message; }
                    finally { tcp.Dispose(); Interlocked.Decrement(ref _incomingConnections); }
                });
            }
        }
        catch (Exception ex) when (ex is OperationCanceledException or SocketException or ObjectDisposedException) { }
    }

    private async Task AcceptClientAsync(TcpClient tcp, CancellationToken token)
    {
        tcp.NoDelay = true;
        var address = ((IPEndPoint)tcp.Client.RemoteEndPoint!).Address;
        if (!IsPrivate(address)) return;
        using var handshake = CancellationTokenSource.CreateLinkedTokenSource(token);
        handshake.CancelAfter(TimeSpan.FromSeconds(10));
        string? remoteId = null;
        using var tls = new SslStream(tcp.GetStream(), false, (_, cert, _, _) =>
        {
            if (cert is null) return false;
            remoteId = IdentityStore.Fingerprint(cert);
            lock (_gate) return _trusted.ContainsKey(remoteId) || (_pairingCode is not null && DateTimeOffset.UtcNow < _pairingExpiry && _pending.Count < 4);
        });
        await tls.AuthenticateAsServerAsync(new SslServerAuthenticationOptions
        {
            ServerCertificate = _identity.Certificate, ClientCertificateRequired = true,
            EnabledSslProtocols = SslProtocols.Tls12 | SslProtocols.Tls13,
            CertificateRevocationCheckMode = X509RevocationMode.NoCheck
        }, handshake.Token);
        var hello = await ReadMessage(tls, handshake.Token);
        if (remoteId is null || remoteId == _identity.DeviceId) throw new AuthenticationException("Invalid peer identity");
        string type = RequiredString(hello, "type");
        if (type == "pair")
        {
            using var pairing = CancellationTokenSource.CreateLinkedTokenSource(token);
            pairing.CancelAfter(TimeSpan.FromMinutes(3));
            string name = RequiredString(hello, "name"); ValidateName(name);
            string clientNonce = RequiredString(hello, "nonce"); ValidateNonce(clientNonce);
            string serverNonce = Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
            int peerPort = Int(hello, "port", 45873); ValidatePort(peerPort);
            int generation;
            lock (_gate)
            {
                if (_pairingCode is null || DateTimeOffset.UtcNow >= _pairingExpiry || RequiredString(hello, "code") != _pairingCode || _pending.Count >= 4)
                    throw new AuthenticationException("设备码错误、已失效，或配对请求过多。");
                // Consume once; a new attempt requires explicitly opening pairing again.
                _pairingCode = null;
                generation = _generation;
            }
            await WriteMessage(tls, new { type = "pair-ready", name = _preferences.Name, nonce = serverNonce }, pairing.Token);
            await ConfirmPairAsync(tls, new(remoteId, name, address.ToString(), peerPort, [1, 2]), clientNonce, serverNonce, true, generation, pairing.Token);
            return;
        }
        bool dataOnly = type == "start-data";
        if (type != "start" && !dataOnly) throw new AuthenticationException("Unsupported control message");
        TrustedPeer trusted;
        Session session;
        byte[] senderKey = RandomNumberGenerator.GetBytes(32), receiverKey = RandomNumberGenerator.GetBytes(32);
        Guid sessionId = Guid.NewGuid();
        string udpToken = Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
        int udpPort;
        lock (_gate)
        {
            if (!_trusted.TryGetValue(remoteId, out trusted!)) throw new AuthenticationException("Device is not paired");
            RequireMode(dataOnly ? "share" : "receive");
            if (dataOnly && !_receivePositions && !_receiveEvents) throw new InvalidOperationException("尚未允许位置或事件接收。");
            if (dataOnly && _shareBlockedPeers.Contains(remoteId)) throw new InvalidOperationException("本机已停止该设备的数据连接。");
            if (_sessions.ContainsKey(remoteId)) throw new InvalidOperationException("该设备已有活动会话，请先停止同步。");
            int[] requested = dataOnly ? [] : Controllers(hello, [1, 2]);
            if (requested.Any(c => !_preferences.Controllers.Contains(c) || !_remoteEnabled[c - 1])) throw new InvalidOperationException("接收端尚未允许所选手柄，请先开启接收。");
            if (_sessions.Values.Any(s => s.Incoming && s.Active && s.Controllers.Intersect(requested).Any())) throw new InvalidOperationException("控制器已被其他发送设备占用。");
            session = new()
            {
                DeviceId = remoteId, Name = trusted.Name, Address = address.ToString(), Token = udpToken, Controllers = requested,
                Id = sessionId, Crypto = new(sessionId, receiverKey, senderKey), Tcp = tcp, Tls = tls, Incoming = true, DataOnly = dataOnly
            };
            foreach (int c in requested) { _remote[c - 1].Reset(); session.Grants[c - 1] = NewGrant(); }
            _sessions[remoteId] = session;
            _peerErrors.Remove(remoteId);
            udpPort = _preferences.Port;
        }
        try
        {
            await WriteMessage(tls, new { type = "session", dataOnly, sessionId, token = udpToken, senderKey = Convert.ToBase64String(senderKey), receiverKey = Convert.ToBase64String(receiverKey), port = udpPort, grants = session.Grants }, handshake.Token);
            await RunControlsAsync(session, token);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(senderKey); CryptographicOperations.ZeroMemory(receiverKey);
            lock (_gate) CloseLocked(session, "control_disconnected");
        }
    }

    private async Task<(TcpClient Tcp, SslStream Tls, string RemoteId)> ConnectTls(string address, int port, string? pinnedId, CancellationToken token)
    {
        var tcp = new TcpClient(AddressFamily.InterNetwork) { NoDelay = true };
        try
        {
            IPAddress bind; lock (_gate) bind = IPAddress.Parse(_preferences.BindAddress);
            tcp.Client.Bind(new IPEndPoint(bind, 0));
            await tcp.ConnectAsync(IPAddress.Parse(address), port, token);
            string? remoteId = null;
            var tls = new SslStream(tcp.GetStream(), false, (_, cert, _, _) =>
            {
                if (cert is null) return false;
                remoteId = IdentityStore.Fingerprint(cert);
                return pinnedId is null || remoteId == pinnedId;
            });
            try
            {
                await tls.AuthenticateAsClientAsync(new SslClientAuthenticationOptions
                {
                    TargetHost = "AutoModules-LAN", ClientCertificates = new X509CertificateCollection { _identity.Certificate },
                    EnabledSslProtocols = SslProtocols.Tls12 | SslProtocols.Tls13,
                    CertificateRevocationCheckMode = X509RevocationMode.NoCheck
                }, token);
                if (remoteId is null || remoteId == _identity.DeviceId) throw new AuthenticationException("Invalid peer identity");
                return (tcp, tls, remoteId);
            }
            catch { tls.Dispose(); throw; }
        }
        catch { tcp.Dispose(); throw; }
    }
    private async Task PairAsync(string address, int port, string code, int generation, CancellationToken token)
    {
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(token);
        deadline.CancelAfter(TimeSpan.FromSeconds(10));
        var connection = await ConnectTls(address, port, null, deadline.Token);
        using var tcp = connection.Tcp; using var tls = connection.Tls;
        string clientNonce = Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
        string name; int localPort;
        lock (_gate) { name = _preferences.Name; localPort = _preferences.Port; }
        await WriteMessage(tls, new { type = "pair", code, name, nonce = clientNonce, port = localPort }, deadline.Token);
        var ready = await ReadMessage(tls, deadline.Token);
        if (RequiredString(ready, "type") != "pair-ready") throw new AuthenticationException("Pairing rejected");
        string remoteName = RequiredString(ready, "name"); ValidateName(remoteName);
        string serverNonce = RequiredString(ready, "nonce"); ValidateNonce(serverNonce);
        using var pairing = CancellationTokenSource.CreateLinkedTokenSource(token);
        pairing.CancelAfter(TimeSpan.FromMinutes(3));
        await ConfirmPairAsync(tls, new(connection.RemoteId, remoteName, address, port, [1, 2]), clientNonce, serverNonce, false, generation, pairing.Token);
    }
    private async Task ConfirmPairAsync(SslStream tls, TrustedPeer peer, string clientNonce, string serverNonce, bool incoming, int generation, CancellationToken token)
    {
        string[] identities = [_identity.DeviceId, peer.DeviceId]; Array.Sort(identities, StringComparer.Ordinal);
        string hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join(":", identities) + ":" + clientNonce + ":" + serverNonce)));
        string fingerprint = string.Join("-", Enumerable.Range(0, 4).Select(i => hash.Substring(i * 4, 4)));
        var request = new PairRequest { Id = Guid.NewGuid().ToString("N"), DeviceId = peer.DeviceId, Name = peer.Name, Fingerprint = fingerprint, Incoming = incoming };
        Guid pairVersion = Guid.NewGuid();
        lock (_gate)
        {
            if (_generation != generation || _disposed || _mode == "off") throw new OperationCanceledException();
            _pending.Add(request.Id, request);
            _pairVersions[peer.DeviceId] = pairVersion;
            _pairingState = "waiting-confirmation";
            _pairingTarget = peer.Name;
        }
        try
        {
            if (!await request.Answer.Task.WaitAsync(token)) throw new AuthenticationException("配对已拒绝。");
            await WriteMessage(tls, new { type = "confirm", fingerprint }, token);
            var remote = await ReadMessage(tls, token);
            if (RequiredString(remote, "type") != "confirm" || RequiredString(remote, "fingerprint") != fingerprint) throw new AuthenticationException("双方校验码不一致。");
            lock (_gate)
            {
                if (_generation != generation || _disposed || _mode == "off" || _pairVersions.GetValueOrDefault(peer.DeviceId) != pairVersion) throw new OperationCanceledException();
                _trusted[peer.DeviceId] = peer; SavePreferencesLater(); _error = null;
                _pairingState = "paired";
                _pairingTarget = peer.Name;
            }
        }
        finally
        {
            lock (_gate)
            {
                _pending.Remove(request.Id);
                if (_pairVersions.GetValueOrDefault(peer.DeviceId) == pairVersion) _pairVersions.Remove(peer.DeviceId);
            }
        }
    }

    private async Task StartOutgoingAsync(TrustedPeer peer, int generation, Guid startVersion, CancellationToken token, bool dataOnly = false)
    {
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(token);
        deadline.CancelAfter(TimeSpan.FromSeconds(10));
        var connection = await ConnectTls(peer.Address, peer.Port, peer.DeviceId, deadline.Token);
        using var tcp = connection.Tcp; using var tls = connection.Tls;
        await WriteMessage(tls, new { type = dataOnly ? "start-data" : "start", controllers = peer.Controllers }, deadline.Token);
        var ready = await ReadMessage(tls, deadline.Token);
        if (RequiredString(ready, "type") != "session") throw new AuthenticationException("Receiver did not permit session");
        if (dataOnly && (!ready.TryGetProperty("dataOnly", out var dataFlag) || !dataFlag.GetBoolean())) throw new AuthenticationException("Receiver does not support data sharing");
        Guid id = Guid.Parse(RequiredString(ready, "sessionId"));
        byte[] tx = Convert.FromBase64String(RequiredString(ready, "senderKey")), rx = Convert.FromBase64String(RequiredString(ready, "receiverKey"));
        var session = new Session
        {
            DeviceId = peer.DeviceId, Name = peer.Name, Address = peer.Address, Token = RequiredString(ready, "token"), Controllers = dataOnly ? [] : peer.Controllers, DataOnly = dataOnly,
            Id = id, Crypto = new(id, tx, rx), Tcp = tcp, Tls = tls
        };
        CryptographicOperations.ZeroMemory(tx); CryptographicOperations.ZeroMemory(rx);
        uint[] grants = ready.GetProperty("grants").EnumerateArray().Select(e => e.GetUInt32()).ToArray();
        if (grants.Length != 2) throw new AuthenticationException("Invalid route grants");
        grants.CopyTo(session.Grants, 0);
        int port = Int(ready, "port", peer.Port); ValidatePort(port);
        BeforeSessionRegistrationForTest?.Invoke(peer.DeviceId);
        lock (_gate)
        {
            if (_generation != generation || _mode != (dataOnly ? "share" : "send") || !_trusted.ContainsKey(peer.DeviceId) || _startVersions.GetValueOrDefault(peer.DeviceId) != startVersion) { session.Crypto.Dispose(); throw new OperationCanceledException(); }
            if (_sessions.TryGetValue(peer.DeviceId, out var activeSession) && activeSession.Active)
            { session.Crypto.Dispose(); throw new InvalidOperationException("设备已有活动连接，请勿双向同时发起。"); }
            _sessions[peer.DeviceId] = session; _peerErrors.Remove(peer.DeviceId); _error = null;
            _connecting.Remove(peer.DeviceId);
            _work.Enqueue(() =>
            {
                NetManager? manager;
                lock (_gate) manager = session.Active && _generation == generation && _startVersions.GetValueOrDefault(peer.DeviceId) == startVersion ? _net : null;
                if (manager is null) return;
                var udpPeer = manager.Connect(peer.Address, port, session.Token);
                bool keep;
                lock (_gate) { keep = session.Active; if (keep) session.Peer = udpPeer; }
                if (!keep) udpPeer?.Disconnect();
            });
        }
        try { await RunControlsAsync(session, token); }
        finally { lock (_gate) CloseLocked(session, "control_disconnected"); }
    }
    private async Task RunControlsAsync(Session session, CancellationToken token)
    {
        using var lifetime = CancellationTokenSource.CreateLinkedTokenSource(token);
        var writer = Task.Run(async () =>
        {
            try { await foreach (var message in session.Controls.Reader.ReadAllAsync(lifetime.Token)) await WriteMessage(session.Tls, message, lifetime.Token); }
            catch (Exception) { session.Tcp.Dispose(); }
        });
        try
        {
            while (!token.IsCancellationRequested)
            {
                var message = await ReadMessage(session.Tls, token);
                if (session.DataOnly)
                {
                    lock (_gate) ReceiveSharedEventLocked(session, message);
                    continue;
                }
                if (RequiredString(message, "type") != "permissions" || session.Incoming) throw new AuthenticationException("Unexpected control message");
                uint[] grants = message.GetProperty("grants").EnumerateArray().Select(v => v.GetUInt32()).ToArray();
                if (grants.Length != 2) throw new AuthenticationException("Invalid grants");
                lock (_gate)
                {
                    if (!session.Active) return;
                    for (int i = 0; i < 2; i++)
                        if (session.Grants[i] != grants[i]) { session.Grants[i] = grants[i]; session.Initialized[i] = false; }
                }
            }
        }
        finally { lifetime.Cancel(); await writer; }
    }

    private static async Task WriteMessage(SslStream tls, object message, CancellationToken token)
    {
        byte[] bytes = JsonSerializer.SerializeToUtf8Bytes(message);
        if (bytes.Length > 8192) throw new InvalidDataException("Control message too large");
        byte[] header = new byte[4]; BinaryPrimitives.WriteInt32BigEndian(header, bytes.Length);
        await tls.WriteAsync(header, token); await tls.WriteAsync(bytes, token); await tls.FlushAsync(token);
    }
    private static async Task<JsonElement> ReadMessage(SslStream tls, CancellationToken token)
    {
        byte[] header = new byte[4]; await tls.ReadExactlyAsync(header, token);
        int length = BinaryPrimitives.ReadInt32BigEndian(header);
        if (length is < 2 or > 8192) throw new InvalidDataException("Invalid control message size");
        byte[] bytes = new byte[length]; await tls.ReadExactlyAsync(bytes, token);
        using var document = JsonDocument.Parse(bytes, new JsonDocumentOptions { MaxDepth = 8 });
        return document.RootElement.Clone();
    }
    private static void ValidateName(string name) { if (name.Length is < 1 or > 64) throw new InvalidDataException("Invalid device name"); }
    private static void ValidateNonce(string nonce) { if (nonce.Length != 64 || !nonce.All(Uri.IsHexDigit)) throw new AuthenticationException("Invalid pairing challenge"); }
    private static uint NewGrant() => (uint)RandomNumberGenerator.GetInt32(1, int.MaxValue);
}
