using System.Net;
using System.Net.Sockets;
using System.Text.Json;

namespace LanInputSync.Tests;

[CollectionDefinition("loopback", DisableParallelization = true)]
public class LoopbackCollection { }

[Collection("loopback")]
public class LoopbackTests
{
    private static JsonElement Call(LanSyncService service, string command, object? args = null)
    {
        var result = JsonSerializer.SerializeToElement(service.Handle(command, JsonSerializer.SerializeToElement(args ?? new { })));
        Assert.True(result.GetProperty("ok").GetBoolean(), result.TryGetProperty("error", out var e) ? e.GetString() : result.ToString());
        return result.GetProperty("status");
    }
    private static async Task Until(Func<bool> test, Func<string>? details = null, int timeout = 7000)
    {
        var end = Environment.TickCount64 + timeout;
        while (Environment.TickCount64 < end) { if (test()) return; await Task.Delay(10); }
        Assert.Fail("Timed out: " + details?.Invoke());
    }
    private static int FreePort()
    {
        for (int i = 0; i < 100; i++)
        {
            int port = Random.Shared.Next(20000, 45000);
            var tcp = new TcpListener(IPAddress.Loopback, port);
            try { using var udp = new UdpClient(new IPEndPoint(IPAddress.Loopback, port)); tcp.Start(); tcp.Stop(); return port; }
            catch (SocketException) { tcp.Stop(); }
        }
        throw new InvalidOperationException("Cannot reserve test port");
    }
    private sealed class Pair : IDisposable
    {
        private readonly string _directory = Path.Combine(Path.GetTempPath(), "lan-sync-tests-" + Guid.NewGuid().ToString("N"));
        public LanSyncService Sender { get; }
        public LanSyncService Receiver { get; }
        public string ReceiverId => Call(Receiver, "sync.status").GetProperty("deviceId").GetString()!;
        public int SenderPort { get; } = FreePort();
        public int ReceiverPort { get; } = FreePort();
        private readonly object _reportsGate = new();
        private readonly PadState[] _states = [PadState.Neutral, PadState.Neutral];
        private readonly bool[] _enabled = new bool[2];
        private readonly Timer _reports;
        public Pair()
        {
            Sender = new(Path.Combine(_directory, "sender")); Receiver = new(Path.Combine(_directory, "receiver"));
            _reports = new Timer(_ => { lock (_reportsGate) for (int i = 0; i < 2; i++) Sender.Publish(i + 1, _states[i], _enabled[i]); }, null, 0, 8);
        }
        public void Publish(int controller, PadState state, bool enabled)
        {
            lock (_reportsGate) { _states[controller - 1] = state; _enabled[controller - 1] = enabled; Sender.Publish(controller, state, enabled); }
        }
        public void StopReports() => _reports.Change(Timeout.Infinite, Timeout.Infinite);
        public string Details() => "S=" + Call(Sender, "sync.status") + " R=" + Call(Receiver, "sync.status");
        public async Task ConfigureAndPair(bool dataOnly = false)
        {
            Call(Sender, "sync.configure", new { mode = dataOnly ? "share" : "send", name = "sender", bindAddress = "127.0.0.1", port = SenderPort, receivePositions = dataOnly, receiveEvents = dataOnly });
            Call(Receiver, "sync.configure", new { mode = dataOnly ? "share" : "receive", name = "receiver", bindAddress = "127.0.0.1", port = ReceiverPort, receivePositions = dataOnly, receiveEvents = dataOnly });
            await Until(() => Call(Sender, "sync.status").GetProperty("networkReady").GetBoolean() && Call(Receiver, "sync.status").GetProperty("networkReady").GetBoolean(), Details);
            string code = Call(Receiver, "sync.pairing").GetProperty("pairingCode").GetString()!;
            Call(Sender, "sync.pair", new { address = "127.0.0.1", port = ReceiverPort, code });
            await Until(() => Call(Sender, "sync.status").GetProperty("pending").GetArrayLength() == 1 && Call(Receiver, "sync.status").GetProperty("pending").GetArrayLength() == 1, Details);
            var a = Call(Sender, "sync.status").GetProperty("pending")[0]; var b = Call(Receiver, "sync.status").GetProperty("pending")[0];
            Assert.Equal(a.GetProperty("fingerprint").GetString(), b.GetProperty("fingerprint").GetString());
            Call(Sender, "sync.confirm", new { requestId = a.GetProperty("requestId").GetString(), allow = true });
            // One-sided confirmation must not establish trust or authorize input.
            await Task.Delay(30); Assert.Empty(Call(Sender, "sync.status").GetProperty("peers").EnumerateArray());
            Call(Receiver, "sync.confirm", new { requestId = b.GetProperty("requestId").GetString(), allow = true });
            await Until(() => Call(Sender, "sync.status").GetProperty("peers").GetArrayLength() == 1 && Call(Receiver, "sync.status").GetProperty("peers").GetArrayLength() == 1, Details);
        }
        public async Task Start()
        {
            Call(Receiver, "sync.start", new { controllers = new[] { 1, 2 } });
            Call(Sender, "sync.start", new { deviceId = ReceiverId, controllers = new[] { 1, 2 } });
            await Until(() => Call(Sender, "sync.status").GetProperty("peers")[0].GetProperty("connected").GetBoolean(), Details);
        }
        public async Task PairAdditional(LanSyncService receiver, int port)
        {
            Call(receiver, "sync.configure", new { mode = "receive", bindAddress = "127.0.0.1", port });
            await Until(() => Call(receiver, "sync.status").GetProperty("networkReady").GetBoolean());
            var code = Call(receiver, "sync.pairing").GetProperty("pairingCode").GetString();
            Call(Sender, "sync.pair", new { address = "127.0.0.1", port, code });
            await Until(() => Call(Sender, "sync.status").GetProperty("pending").GetArrayLength() == 1 && Call(receiver, "sync.status").GetProperty("pending").GetArrayLength() == 1);
            var a = Call(Sender, "sync.status").GetProperty("pending")[0]; var b = Call(receiver, "sync.status").GetProperty("pending")[0];
            Assert.Equal(a.GetProperty("fingerprint").GetString(), b.GetProperty("fingerprint").GetString());
            Call(Sender, "sync.confirm", new { requestId = a.GetProperty("requestId").GetString() });
            Call(receiver, "sync.confirm", new { requestId = b.GetProperty("requestId").GetString() });
            await Until(() => Call(Sender, "sync.status").GetProperty("peers").GetArrayLength() == 2 && Call(receiver, "sync.status").GetProperty("peers").GetArrayLength() == 1);
        }
        public void Dispose()
        {
            _reports.Dispose(); Sender.Dispose(); Receiver.Dispose();
            // This test owns its randomly generated private directory only.
            if (Directory.Exists(_directory)) Directory.Delete(_directory, true);
        }
    }

    [Fact]
    public async Task SharedPositionsAndEventsDoNotOwnControllers()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair(dataOnly: true);
        // Event-only channels must remain startable when both controller
        // scopes are intentionally empty.
        Call(pair.Sender, "sync.configure", new { mode = "share", name = "sender", bindAddress = "127.0.0.1", port = pair.SenderPort, controllers = Array.Empty<int>(), receivePositions = true, receiveEvents = true });
        Call(pair.Receiver, "sync.configure", new { mode = "share", name = "receiver", bindAddress = "127.0.0.1", port = pair.ReceiverPort, controllers = Array.Empty<int>(), receivePositions = true, receiveEvents = true });
        await Until(() => Call(pair.Sender, "sync.status").GetProperty("networkReady").GetBoolean() && Call(pair.Receiver, "sync.status").GetProperty("networkReady").GetBoolean(), pair.Details);
        Assert.False(pair.Receiver.OwnsController(1));
        Assert.False(pair.Receiver.OwnsController(2));
        Call(pair.Sender, "sync.start", new { deviceId = pair.ReceiverId });
        await Until(() => Call(pair.Sender, "sync.status").GetProperty("peers")[0].GetProperty("connected").GetBoolean(), pair.Details);
        Call(pair.Sender, "sync.share.position", new { actorId = "expired", mapId = "map", mapVersion = "base", x = 99.0, y = 99.0, confidence = .9, ageMs = 0, deadlineMs = Environment.TickCount64 - 1 });
        Call(pair.Sender, "sync.share.event", new { deviceId = pair.ReceiverId, name = "expired", targets = new[] { "A1" }, deadlineMs = Environment.TickCount64 - 1 });
        await Task.Delay(50);
        Assert.Empty(Call(pair.Receiver, "sync.status").GetProperty("sharedPositions").EnumerateArray());
        Assert.Equal(0, Call(pair.Receiver, "sync.status").GetProperty("pendingSharedEvents").GetInt32());
        Call(pair.Sender, "sync.share.position", new { actorId = "B", mapId = "map", mapVersion = "base", x = 12.5, y = 24.0, confidence = .9, ageMs = 0 });
        await Until(() => Call(pair.Receiver, "sync.status").GetProperty("sharedPositions").GetArrayLength() == 1, pair.Details);
        Call(pair.Sender, "sync.share.event", new { deviceId = pair.ReceiverId, name = "start_follow", targets = new[] { "A1", "A2" } });
        await Until(() => Call(pair.Receiver, "sync.status").GetProperty("pendingSharedEvents").GetInt32() == 1, pair.Details);
        var received = JsonSerializer.SerializeToElement(pair.Receiver.Handle("sync.share.drain", JsonSerializer.SerializeToElement(new { })));
        Assert.Equal("start_follow", received.GetProperty("events")[0].GetProperty("name").GetString());
        Assert.False(pair.Receiver.OwnsController(1));
        Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
        await Task.Delay(700);
        Assert.Empty(Call(pair.Receiver, "sync.status").GetProperty("sharedPositions").EnumerateArray());
        pair.Receiver.EmergencyStop();
        Assert.False(Call(pair.Receiver, "sync.status").GetProperty("receiveEvents").GetBoolean());
        Assert.False(Call(pair.Receiver, "sync.status").GetProperty("receivePositions").GetBoolean());
        Assert.False(pair.Receiver.OwnsController(1));
    }

    [Fact]
    public async Task SharedEventCatalogIsDeliveredWithoutControllerOwnership()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair(dataOnly: true);
        Call(pair.Sender, "sync.start", new { deviceId = pair.ReceiverId });
        await Until(() => Call(pair.Sender, "sync.status").GetProperty("peers")[0].GetProperty("connected").GetBoolean(), pair.Details);
        await Until(() =>
        {
            try
            {
                Call(pair.Sender, "sync.share.catalog", new { deviceId = pair.ReceiverId, catalog = new {
                    deviceId = "sender", catalogRevision = 1, catalogHash = "hash", events = Array.Empty<object>(),
                    definitions = new[] { new { id = "event-a", name = "A event", owner_device_id = "sender", revision = 1, tracks = Array.Empty<object>() } }
                }});
                return true;
            }
            catch { return false; }
        }, pair.Details);
        await Until(() => Call(pair.Receiver, "sync.status").GetProperty("pendingSharedCatalogs").GetInt32() == 1, pair.Details);
        var received = JsonSerializer.SerializeToElement(pair.Receiver.Handle("sync.share.drain", JsonSerializer.SerializeToElement(new { })));
        Assert.Equal("sender", received.GetProperty("catalogs")[0].GetProperty("deviceId").GetString());
        Assert.False(pair.Receiver.OwnsController(1));
    }

    [Fact]
    public async Task CatalogDrainDoesNotConsumeSharedEvents()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair(dataOnly: true);
        Call(pair.Sender, "sync.start", new { deviceId = pair.ReceiverId });
        await Until(() => Call(pair.Sender, "sync.status").GetProperty("peers")[0].GetProperty("connected").GetBoolean(), pair.Details);

        await Until(() =>
        {
            try
            {
                Call(pair.Sender, "sync.share.catalog", new { deviceId = pair.ReceiverId, catalog = new {
                    deviceId = "sender", catalogRevision = 1, catalogHash = "hash", events = Array.Empty<object>(),
                    definitions = new[] { new { id = "event-a", name = "A event", owner_device_id = "sender", revision = 1, tracks = Array.Empty<object>() } }
                }});
                Call(pair.Sender, "sync.share.event", new { deviceId = pair.ReceiverId, name = "A event", eventId = "event-a", eventRevision = 1,
                    targets = new[] { "1" }, deadlineMs = Environment.TickCount64 + 400 });
                return true;
            }
            catch { return false; }
        }, pair.Details);
        await Until(() => Call(pair.Receiver, "sync.status").GetProperty("pendingSharedEvents").GetInt32() == 1
            && Call(pair.Receiver, "sync.status").GetProperty("pendingSharedCatalogs").GetInt32() == 1, pair.Details);

        var catalogs = JsonSerializer.SerializeToElement(pair.Receiver.Handle("sync.share.catalog_drain", JsonSerializer.SerializeToElement(new { })));
        Assert.Single(catalogs.GetProperty("catalogs").EnumerateArray());
        Assert.Equal(1, Call(pair.Receiver, "sync.status").GetProperty("pendingSharedEvents").GetInt32());
        var events = JsonSerializer.SerializeToElement(pair.Receiver.Handle("sync.share.drain", JsonSerializer.SerializeToElement(new { })));
        Assert.Single(events.GetProperty("events").EnumerateArray());
        Assert.Empty(events.GetProperty("catalogs").EnumerateArray());
    }

    [Fact]
    public async Task RealTlsUdpTwoSlotsShortTapAndIndependentReceiverPause()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair(); await pair.Start();
        pair.Publish(1, new(LeftStickY: 32767), true);
        pair.Publish(2, new(RightStickX: -18000, LeftTrigger: 123), true);
        await Until(() => pair.Receiver.Consume(1).LeftStickY == 32767 && pair.Receiver.Consume(2).RightStickX == -18000, pair.Details);
        // Both publication calls may fall between network polls. They must remain distinct reports.
        pair.Publish(1, new(0x1000, LeftStickY: 32767), true);
        pair.Publish(1, new(0, LeftStickY: 32767), true);
        await Until(() => pair.Receiver.Consume(1).Buttons == 0x1000, pair.Details);
        Assert.Equal(0, pair.Receiver.Consume(1).Buttons);
        pair.Receiver.SetRemoteEnabled(1, false);
        Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
        await Task.Delay(50);
        Assert.Equal(-18000, pair.Receiver.Consume(2).RightStickX);
        pair.Receiver.SetRemoteEnabled(1, true);
        await Until(() => pair.Receiver.Consume(1).LeftStickY == 32767, pair.Details);
        pair.Publish(1, new(LeftStickY: 32767), false);
        await Until(() => pair.Receiver.Consume(1) == PadState.Neutral, pair.Details);
        pair.Publish(1, new(LeftStickX: 10000), true);
        await Until(() => pair.Receiver.Consume(1).LeftStickX == 10000, pair.Details);
        pair.Receiver.EmergencyStop();
        Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
        await Task.Delay(100);
        Assert.False(pair.Receiver.IsRemoteEnabled(1));
        Assert.False(pair.Receiver.IsRemoteEnabled(2));
    }

    [Fact]
    public async Task ReceiverRequiresExplicitPermissionAndSenderCloseReleasesAll()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair();
        Call(pair.Sender, "sync.start", new { deviceId = pair.ReceiverId, controllers = new[] { 1, 2 } });
        await Task.Delay(200);
        Assert.False(pair.Receiver.IsRemoteEnabled(1));
        Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
        await pair.Start();
        pair.Publish(1, new(0x1000, LeftStickY: 32767), true);
        await Until(() => pair.Receiver.Consume(1).Buttons == 0x1000, pair.Details);
        pair.Sender.Dispose();
        await Until(() => !pair.Receiver.IsRemoteEnabled(1), () => Call(pair.Receiver, "sync.status").ToString());
        Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
    }

    [Fact]
    public async Task WrongDeviceCodeCannotCreateTrustOrOutput()
    {
        using var pair = new Pair();
        Call(pair.Sender, "sync.configure", new { mode = "send", bindAddress = "127.0.0.1", port = pair.SenderPort });
        Call(pair.Receiver, "sync.configure", new { mode = "receive", bindAddress = "127.0.0.1", port = pair.ReceiverPort });
        await Task.Delay(150);
        string correct = Call(pair.Receiver, "sync.pairing").GetProperty("pairingCode").GetString()!;
        string wrong = correct == "00000000" ? "11111111" : "00000000";
        Call(pair.Sender, "sync.pair", new { address = "127.0.0.1", port = pair.ReceiverPort, code = wrong });
        await Until(() => Call(pair.Sender, "sync.status").GetProperty("error").ValueKind == JsonValueKind.String, pair.Details);
        Assert.Empty(Call(pair.Sender, "sync.status").GetProperty("peers").EnumerateArray());
        Assert.Empty(Call(pair.Receiver, "sync.status").GetProperty("pending").EnumerateArray());
        Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
    }

    [Fact]
    public async Task MissingStateCannotBeKeptAliveByHealthyControlAndProbeTraffic()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair(); await pair.Start();
        pair.Publish(1, new(LeftStickY: 32767), true);
        await Until(() => pair.Receiver.Consume(1).LeftStickY == 32767, pair.Details);
        pair.Sender.SuppressDatagramForTest = lane => lane == 0;
        long began = Environment.TickCount64;
        await Until(() => !pair.Receiver.IsRemoteEnabled(1), pair.Details, 1500);
        Assert.InRange(Environment.TickCount64 - began, 150, 1000);
        Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
        pair.Sender.SuppressDatagramForTest = null;
        await Task.Delay(100);
        Assert.False(pair.Receiver.IsRemoteEnabled(1));
    }

    [Fact]
    public async Task OutputWatchdogStillReleasesWhenReceiverNetworkWorkerIsStalled()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair(); await pair.Start();
        pair.Publish(1, new(LeftStickY: 32767), true);
        await Until(() => pair.Receiver.Consume(1).LeftStickY == 32767, pair.Details);
        using var entered = new ManualResetEventSlim(); using var release = new ManualResetEventSlim();
        pair.Receiver.BeforePollForTest = () => { entered.Set(); release.Wait(TimeSpan.FromSeconds(3)); };
        try
        {
            Assert.True(entered.Wait(TimeSpan.FromSeconds(1)));
            await Task.Delay(250);
            Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
            Assert.False(pair.Receiver.IsRemoteEnabled(1));
        }
        finally { pair.Receiver.BeforePollForTest = null; release.Set(); }
    }

    [Fact]
    public async Task StalledSourceReportLoopCannotStreamHeldInputForever()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair(); await pair.Start();
        pair.Publish(1, new(LeftStickY: 32767), true);
        await Until(() => pair.Receiver.Consume(1).LeftStickY == 32767, pair.Details);
        pair.StopReports();
        await Until(() => !pair.Receiver.IsRemoteEnabled(1), pair.Details, 1500);
        Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
    }

    [Fact]
    public async Task CertificateReplacementAtSavedAddressIsRejected()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair();
        string receiverId = pair.ReceiverId;
        pair.Receiver.Dispose();
        string temp = Path.Combine(Path.GetTempPath(), "lan-impostor-" + Guid.NewGuid().ToString("N"));
        try
        {
            using var impostor = new LanSyncService(temp);
            Call(impostor, "sync.configure", new { mode = "receive", bindAddress = "127.0.0.1", port = pair.ReceiverPort });
            await Task.Delay(100); Call(impostor, "sync.pairing");
            Call(pair.Sender, "sync.start", new { deviceId = receiverId, controllers = new[] { 1, 2 } });
            await Until(() => Call(pair.Sender, "sync.status").GetProperty("error").ValueKind == JsonValueKind.String,
                () => Call(pair.Sender, "sync.status").ToString());
            Assert.False(Call(pair.Sender, "sync.status").GetProperty("peers")[0].GetProperty("connected").GetBoolean());
            Assert.Equal(PadState.Neutral, impostor.Consume(1));
        }
        finally { if (Directory.Exists(temp)) Directory.Delete(temp, true); }
    }

    [Fact]
    public async Task MultipleReceiversSelectDifferentSlotsAndOneStopDoesNotStopOther()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair();
        string temp = Path.Combine(Path.GetTempPath(), "lan-second-receiver-" + Guid.NewGuid().ToString("N"));
        try
        {
            using var second = new LanSyncService(temp); await pair.PairAdditional(second, FreePort());
            string secondId = Call(second, "sync.status").GetProperty("deviceId").GetString()!;
            Call(pair.Receiver, "sync.start", new { controllers = new[] { 1 } });
            Call(second, "sync.start", new { controllers = new[] { 2 } });
            Call(pair.Sender, "sync.start", new { deviceId = pair.ReceiverId, controllers = new[] { 1 } });
            Call(pair.Sender, "sync.start", new { deviceId = secondId, controllers = new[] { 2 } });
            pair.Publish(1, new(LeftStickX: 21000), true); pair.Publish(2, new(LeftStickY: -23000), true);
            await Until(() => pair.Receiver.Consume(1).LeftStickX == 21000 && second.Consume(2).LeftStickY == -23000, pair.Details);
            Assert.Equal(PadState.Neutral, pair.Receiver.Consume(2)); Assert.Equal(PadState.Neutral, second.Consume(1));
            Call(pair.Sender, "sync.stop", new { deviceId = pair.ReceiverId });
            await Until(() => !pair.Receiver.IsRemoteEnabled(1), pair.Details);
            await Task.Delay(80);
            Assert.Equal(-23000, second.Consume(2).LeftStickY);
            // Restart the first route, then stall only its receiver network thread.
            Call(pair.Receiver, "sync.start", new { controllers = new[] { 1 } });
            Call(pair.Sender, "sync.start", new { deviceId = pair.ReceiverId, controllers = new[] { 1 } });
            await Until(() => pair.Receiver.Consume(1).LeftStickX == 21000, pair.Details);
            using var entered = new ManualResetEventSlim(); using var release = new ManualResetEventSlim();
            pair.Receiver.BeforePollForTest = () => { entered.Set(); release.Wait(TimeSpan.FromSeconds(3)); };
            try
            {
                Assert.True(entered.Wait(TimeSpan.FromSeconds(1)));
                pair.Publish(2, new(LeftStickY: 19000), true);
                await Until(() => second.Consume(2).LeftStickY == 19000, pair.Details);
                await Task.Delay(250);
                Assert.Equal(19000, second.Consume(2).LeftStickY);
                Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
            }
            finally { pair.Receiver.BeforePollForTest = null; release.Set(); }
        }
        finally { if (Directory.Exists(temp)) Directory.Delete(temp, true); }
    }

    [Fact]
    public async Task ConfigureThenEmergencyBeforeWorkerRunsStillStartsNeutralListener()
    {
        using var pair = new Pair();
        using var entered = new ManualResetEventSlim(); using var release = new ManualResetEventSlim();
        pair.Receiver.BeforePollForTest = () => { entered.Set(); release.Wait(TimeSpan.FromSeconds(3)); };
        try
        {
            Assert.True(entered.Wait(TimeSpan.FromSeconds(1)));
            Call(pair.Receiver, "sync.configure", new { mode = "receive", bindAddress = "127.0.0.1", port = pair.ReceiverPort });
            pair.Receiver.EmergencyStop();
        }
        finally { pair.Receiver.BeforePollForTest = null; release.Set(); }
        await Until(() => Call(pair.Receiver, "sync.status").GetProperty("networkReady").GetBoolean());
        Assert.NotNull(Call(pair.Receiver, "sync.pairing").GetProperty("pairingCode").GetString());
        Assert.False(pair.Receiver.IsRemoteEnabled(1));
        using var tcp = new TcpClient(); await tcp.ConnectAsync(IPAddress.Loopback, pair.ReceiverPort);
        Assert.True(tcp.Connected);
    }

    [Fact]
    public async Task LostReliableButtonChangeTerminatesRouteRatherThanExecutingBacklog()
    {
        using var pair = new Pair(); await pair.ConfigureAndPair(); await pair.Start();
        pair.Publish(1, new(LeftStickY: 32767), true);
        await Until(() => pair.Receiver.Consume(1).LeftStickY == 32767, pair.Details);
        pair.Sender.SuppressDatagramForTest = lane => lane == 1;
        pair.Publish(1, new(0x1000, LeftStickY: 32767), true);
        await Until(() => !pair.Receiver.IsRemoteEnabled(1), pair.Details, 1500);
        Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
        pair.Sender.SuppressDatagramForTest = null;
        pair.Publish(1, new(LeftStickY: -12000), true);
        await pair.Start();
        await Until(() => pair.Receiver.Consume(1).LeftStickY == -12000, pair.Details);
        Assert.Equal(0, pair.Receiver.Consume(1).Buttons);
    }

    [Theory]
    [InlineData("sync.stop")]
    [InlineData("sync.forget")]
    public async Task SelectedCancellationFencesThatPendingStartWithoutCancelingOtherPeer(string command)
    {
        using var pair = new Pair(); await pair.ConfigureAndPair();
        string temp = Path.Combine(Path.GetTempPath(), "lan-pending-peer-" + Guid.NewGuid().ToString("N"));
        try
        {
            using var second = new LanSyncService(temp); await pair.PairAdditional(second, FreePort());
            string firstId = pair.ReceiverId, secondId = Call(second, "sync.status").GetProperty("deviceId").GetString()!;
            Call(pair.Receiver, "sync.start", new { controllers = new[] { 1 } });
            Call(second, "sync.start", new { controllers = new[] { 2 } });
            using var enteredA = new ManualResetEventSlim(); using var enteredB = new ManualResetEventSlim(); using var release = new ManualResetEventSlim();
            pair.Sender.BeforeSessionRegistrationForTest = id =>
            {
                if (id == firstId) enteredA.Set(); else if (id == secondId) enteredB.Set();
                release.Wait(TimeSpan.FromSeconds(3));
            };
            try
            {
                Call(pair.Sender, "sync.start", new { deviceId = firstId, controllers = new[] { 1 } });
                Call(pair.Sender, "sync.start", new { deviceId = secondId, controllers = new[] { 2 } });
                Assert.True(enteredA.Wait(TimeSpan.FromSeconds(2))); Assert.True(enteredB.Wait(TimeSpan.FromSeconds(2)));
                Call(pair.Sender, command, new { deviceId = firstId });
            }
            finally { pair.Sender.BeforeSessionRegistrationForTest = null; release.Set(); }
            pair.Publish(1, new(LeftStickY: 32000), true); pair.Publish(2, new(LeftStickX: 24000), true);
            await Until(() => second.Consume(2).LeftStickX == 24000, () => Call(pair.Sender, "sync.status").ToString());
            await Until(() => !pair.Receiver.IsRemoteEnabled(1), () => Call(pair.Receiver, "sync.status").ToString());
            Assert.Equal(PadState.Neutral, pair.Receiver.Consume(1));
            Assert.Equal(24000, second.Consume(2).LeftStickX);
        }
        finally { if (Directory.Exists(temp)) Directory.Delete(temp, true); }
    }
}
