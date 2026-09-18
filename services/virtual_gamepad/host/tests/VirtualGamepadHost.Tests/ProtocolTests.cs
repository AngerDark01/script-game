using System.Text.Json;
using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.Protocol;
using VirtualGamepadHost.Runtime;
using VirtualGamepadHost.State;

namespace VirtualGamepadHost.Tests;

public sealed class ProtocolTests
{
    [Fact]
    public void ControllerTwoCommandsDoNotChangeControllerOne()
    {
        var backend = new FakeXInputBackend(2);
        var registry = ControllerRegistry.CreateDefault(backend);
        var router = new CommandRouter(registry, () => new HostStatus(RunState.Ready, true, true, "test"), () => true);
        var start = ProtocolSerializer.Parse("{\"id\":\"1\",\"type\":\"start\",\"payload\":{\"controller\":2}}");
        var command = ProtocolSerializer.Parse("{\"id\":\"2\",\"type\":\"button\",\"payload\":{\"controller\":2,\"source\":\"test\",\"button\":\"A\",\"action\":\"press\"}}");

        Assert.Contains("\"ok\":true", router.Handle(start));
        Assert.Contains("\"ok\":true", router.Handle(command));
        Assert.False(registry[1].Store.Snapshot().IsPressed(GamepadButton.A));
        Assert.True(registry[2].Store.Snapshot().IsPressed(GamepadButton.A));
    }
    [Fact]
    public void RouterAcceptsButtonAndAxisCommands()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var router = new CommandRouter(
            store,
            safety,
            () => new HostStatus(safety.RunState, true, true, "test"));

        var button = ProtocolSerializer.Parse("{\"id\":\"1\",\"type\":\"button\",\"payload\":{\"source\":\"test\",\"button\":\"A\",\"action\":\"press\"}}");
        var axis = ProtocolSerializer.Parse("{\"id\":\"2\",\"type\":\"set_axis\",\"payload\":{\"source\":\"test\",\"axis\":\"left_y\",\"value\":32767}}");

        safety.Start();
        Assert.Contains("\"ok\":true", router.Handle(button));
        Assert.Contains("\"ok\":true", router.Handle(axis));
        Assert.True(store.Snapshot().IsPressed(GamepadButton.A));
        Assert.Equal((short)32767, store.Snapshot().LeftStickY);
    }

    [Fact]
    public void RouterRejectsUnknownTypesAndInvalidAxes()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var router = new CommandRouter(store, safety, () => new HostStatus(safety.RunState, true, true, "test"));

        var unknown = ProtocolSerializer.Parse("{\"id\":\"x\",\"type\":\"nope\",\"payload\":{}}");
        var invalid = ProtocolSerializer.Parse("{\"id\":\"y\",\"type\":\"set_axis\",\"payload\":{\"source\":\"test\",\"axis\":\"bad\",\"value\":0}}");

        Assert.Contains("unknown_type", router.Handle(unknown));
        Assert.Contains("invalid_argument", router.Handle(invalid));
    }

    [Fact]
    public void StartIsRejectedWhenTheVirtualDeviceIsUnavailable()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var router = new CommandRouter(store, safety, () => new HostStatus(safety.RunState, false, false, "missing"), deviceReady: () => false);
        var start = ProtocolSerializer.Parse("{\"id\":\"1\",\"type\":\"start\",\"payload\":{}}");

        Assert.Contains("device_unavailable", router.Handle(start));
        Assert.Equal(RunState.Paused, safety.RunState);
    }

    [Fact]
    public void FencedLifecycleRejectsDelayedStartAfterNewerPauseOrReset()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var router = new CommandRouter(store, safety, () => new HostStatus(safety.RunState, true, true, "test"));

        var start = ProtocolSerializer.Parse("{\"id\":\"1\",\"type\":\"start\",\"payload\":{\"source\":\"page-a\",\"sequence\":10}}");
        var pause = ProtocolSerializer.Parse("{\"id\":\"2\",\"type\":\"pause\",\"payload\":{\"source\":\"page-a\",\"sequence\":20}}");
        var staleStart = ProtocolSerializer.Parse("{\"id\":\"3\",\"type\":\"start\",\"payload\":{\"source\":\"page-a\",\"sequence\":10}}");
        var reset = ProtocolSerializer.Parse("{\"id\":\"4\",\"type\":\"reset\",\"payload\":{\"source\":\"page-a\",\"sequence\":21}}");
        var newerStart = ProtocolSerializer.Parse("{\"id\":\"5\",\"type\":\"start\",\"payload\":{\"source\":\"page-a\",\"sequence\":22}}");

        Assert.Contains("\"accepted\":true", router.Handle(start));
        Assert.Equal(RunState.Running, safety.RunState);
        Assert.Contains("\"accepted\":true", router.Handle(pause));
        Assert.Equal(RunState.Paused, safety.RunState);
        Assert.Contains("\"stale\":true", router.Handle(staleStart));
        Assert.Equal(RunState.Paused, safety.RunState);
        Assert.Contains("\"accepted\":true", router.Handle(reset));
        Assert.Equal(RunState.Paused, safety.RunState);
        Assert.Contains("\"accepted\":true", router.Handle(newerStart));
        Assert.Equal(RunState.Running, safety.RunState);
    }

    [Fact]
    public void LegacyLifecycleCommandsRemainUnfencedAfterSequencedPageCommands()
    {
        var store = new StateStore();
        var safety = new SafetyController(store);
        var router = new CommandRouter(store, safety, () => new HostStatus(safety.RunState, true, true, "test"));

        var fencedPause = ProtocolSerializer.Parse("{\"id\":\"1\",\"type\":\"pause\",\"payload\":{\"source\":\"page-a\",\"sequence\":10}}");
        var legacyStart = ProtocolSerializer.Parse("{\"id\":\"2\",\"type\":\"start\",\"payload\":{}}");

        Assert.Contains("\"accepted\":true", router.Handle(fencedPause));
        Assert.Equal(RunState.Paused, safety.RunState);
        Assert.Contains("\"accepted\":true", router.Handle(legacyStart));
        Assert.Equal(RunState.Running, safety.RunState);
    }
}
