using System.Text.Json;
using LanInputSync;
using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Input;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.Runtime;
using VirtualGamepadHost.State;
using VirtualGamepadHost.Protocol;

namespace VirtualGamepadHost.Tests;

public sealed class LanIntegrationTests
{
    [Fact]
    public void ReceiverOwnsOnlySelectedSlotAndNeverSuppressesItsPhysicalBindings()
    {
        var service = new FakeSync();
        var registry = Registry(service);
        registry[1].Safety.Start(); // Even pre-existing local start must not grant input ownership.
        registry[2].Safety.Start();
        var w = new PhysicalInput("keyboard:W", PhysicalInputType.KeyDown);
        registry.ApplyPhysical(w);
        Assert.Equal(GamepadState.Neutral, registry[1].Store.Snapshot());
        Assert.Equal(short.MaxValue, registry[2].Store.Snapshot().LeftStickY);
        registry[2].Safety.Pause();
        Assert.False(registry.ShouldSuppressPhysical(w));
        Assert.Throws<RemoteOwnershipException>(() => registry.ExecuteLocal(1, slot => slot.Store.SetAxis("test", GamepadAxis.LeftY, 1)));
    }

    [Fact]
    public void StatusDoesNotConsumeButtonTransitionsAndRemoteOutputIsNeverRepublished()
    {
        var service = new FakeSync();
        var registry = Registry(service);
        registry.SubmitAll();
        var first = registry.EffectiveState(1);
        Assert.Equal((ushort)4096, first.Buttons);
        Assert.Equal(first, registry.EffectiveState(1));
        Assert.Equal(1, service.Consumed);
        Assert.DoesNotContain(1, service.Published);
        Assert.Contains(2, service.Published);
    }

    [Fact]
    public void RemoteHotkeyAndEmergencyResetLeaveLocalMappingPaused()
    {
        var service = new FakeSync();
        var registry = Registry(service);
        registry.ToggleController(1);
        Assert.False(service.Enabled);
        registry.ToggleController(1);
        Assert.True(service.Enabled);
        Assert.Equal(RunState.Paused, registry[1].Safety.RunState);
        registry.EmergencyResetAll();
        Assert.True(service.Stopped);
        Assert.Equal(GamepadState.Neutral, registry.EffectiveState(1));
    }

    [Fact]
    public void LeavingReceiverModeClearsLocalInputsBeforeReturningOwnership()
    {
        var service = new FakeSync();
        var registry = Registry(service);
        registry[1].Safety.Start();
        registry[1].Store.SetState("old", GamepadState.Neutral.WithAxis(GamepadAxis.LeftY, 32767));
        registry.HandleSync("sync.configure", JsonSerializer.SerializeToElement(new { mode = "off" }));
        Assert.False(registry.IsRemote(1));
        registry.Lifecycle(1, "start");
        Assert.Equal(GamepadState.Neutral, registry.EffectiveState(1));
    }

    [Fact]
    public void LateUiStartCannotUndoNewerStop()
    {
        var service = new FakeSync();
        var registry = Registry(service);
        registry.HandleSync("sync.stop", JsonSerializer.SerializeToElement(new { _uiSource = "ui", _uiSequence = 2 }));
        registry.HandleSync("sync.start", JsonSerializer.SerializeToElement(new { _uiSource = "ui", _uiSequence = 1 }));
        Assert.Equal(new[] { "sync.stop" }, service.Commands);
    }

    [Fact]
    public void PipeAutomationIsRejectedForRemoteSlotWhileSecondSlotRemainsUsable()
    {
        var service = new FakeSync();
        var registry = Registry(service);
        var router = new CommandRouter(registry, () => new HostStatus(RunState.Paused, true, true, ""));
        var rejected = router.Handle(ProtocolSerializer.Parse("""{"type":"set_axis","payload":{"controller":1,"source":"test","axis":"left_y","value":32767}}"""));
        Assert.Equal("slot_owned_by_remote", JsonDocument.Parse(rejected).RootElement.GetProperty("error").GetProperty("code").GetString());
        var accepted = router.Handle(ProtocolSerializer.Parse("""{"type":"set_axis","payload":{"controller":2,"source":"test","axis":"left_y","value":32767}}"""));
        Assert.True(JsonDocument.Parse(accepted).RootElement.GetProperty("ok").GetBoolean());
        Assert.Equal(0, service.Consumed);
    }

    [Fact]
    public void EventChannelOverlaysRemoteControllerWithoutTakingOwnership()
    {
        var service = new FakeSync();
        var registry = Registry(service);

        registry.SetEventState(1, "event:remote", GamepadState.Neutral.WithButton(GamepadButton.B, true), TimeSpan.FromSeconds(1));

        // The receive channel supplies A; the independent event channel must
        // add B instead of being rejected or replacing the remote state.
        registry.SubmitAll();

        var state = registry.EffectiveState(1);
        Assert.True(state.IsPressed(GamepadButton.A));
        Assert.True(state.IsPressed(GamepadButton.B));
    }

    [Fact]
    public void ReceptionPermissionWithoutLiveSenderIsPausedButHotkeyRevokesPermission()
    {
        var service = new FakeSync { Active = false };
        var registry = Registry(service);
        registry.SubmitAll();
        Assert.Equal(RunState.Paused, registry.EffectiveRunState(1));
        Assert.Equal(GamepadState.Neutral, registry.EffectiveState(1));
        registry.ToggleController(1);
        Assert.False(service.Enabled);
    }

    [Fact]
    public void StopIsSafeWhenLanServiceCouldNotBeInitialized()
    {
        var registry = ControllerRegistry.CreateDefault(new NullXInputBackend());
        var router = new CommandRouter(registry, () => new HostStatus(RunState.Paused, true, true, ""));
        var response = router.Handle(ProtocolSerializer.Parse("""{"type":"sync.stop","payload":{}}"""));
        Assert.True(JsonDocument.Parse(response).RootElement.GetProperty("ok").GetBoolean());
        response = router.Handle(ProtocolSerializer.Parse("""{"type":"sync.suspend","payload":{}}"""));
        Assert.True(JsonDocument.Parse(response).RootElement.GetProperty("ok").GetBoolean());
    }

    [Theory]
    [InlineData("{\"_uiSource\":\"ui\"}")]
    [InlineData("{\"_uiSequence\":1}")]
    [InlineData("{\"_uiSource\":\"ui\",\"_uiSequence\":-1}")]
    public void MalformedUiFenceIsRejectedWithoutExecutingCommand(string payload)
    {
        var service = new FakeSync();
        var router = new CommandRouter(Registry(service), () => new HostStatus(RunState.Paused, true, true, ""));
        var response = router.Handle(ProtocolSerializer.Parse("{\"type\":\"sync.start\",\"payload\":" + payload + "}"));
        Assert.Equal("invalid_argument", JsonDocument.Parse(response).RootElement.GetProperty("error").GetProperty("code").GetString());
        Assert.Empty(service.Commands);
    }

    private static ControllerRegistry Registry(FakeSync service)
    {
        var backend = new NullXInputBackend();
        backend.Start();
        var registry = ControllerRegistry.CreateDefault(backend);
        registry.AttachSync(service);
        return registry;
    }

    private sealed class FakeSync : ILanSyncService
    {
        public bool Enabled = true;
        public bool Active = true;
        public bool Stopped;
        public int Consumed;
        public List<int> Published = new();
        public List<string> Commands = new();
        private bool _owns = true;
        public void Publish(int controller, PadState state, bool enabled) => Published.Add(controller);
        public bool OwnsController(int controller) => _owns && controller == 1;
        public PadState Consume(int controller) { Consumed++; return Enabled ? new PadState(4096) : PadState.Neutral; }
        public bool IsRemoteEnabled(int controller) => Enabled;
        public bool IsRemoteActive(int controller) => Enabled && Active;
        public void SetRemoteEnabled(int controller, bool enabled) => Enabled = enabled;
        public void EmergencyStop() { Stopped = true; Enabled = false; }
        public object Handle(string command, JsonElement payload)
        {
            Commands.Add(command);
            if (command == "sync.configure") _owns = false;
            return new { ok = true };
        }
        public void Dispose() { }
    }
}
