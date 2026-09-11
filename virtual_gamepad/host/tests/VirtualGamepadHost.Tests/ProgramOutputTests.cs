using System.Text.Json;
using VirtualGamepadHost.Driver;
using VirtualGamepadHost.Input;
using VirtualGamepadHost.Model;
using VirtualGamepadHost.Runtime;

namespace VirtualGamepadHost.Tests;

public class ProgramOutputTests
{
    private static JsonElement Payload(object value) => JsonSerializer.SerializeToElement(value);

    [Fact]
    public void ProgramOutputNeverArmsPhysicalMappingAndPauseRevokesToken()
    {
        var registry = ControllerRegistry.CreateDefault(new NullXInputBackend());
        var reply = JsonSerializer.SerializeToElement(registry.HandleProgram("program.acquire", Payload(new { controller = 1 })));
        var token = reply.GetProperty("token").GetString()!;
        registry.HandleProgram("program.state", Payload(new { controller = 1, token, ttlMs = 100, state = new GamepadState(0, 0, 0, 20000, 0, 0, 0) }));
        Assert.Equal(20000, registry.EffectiveState(1).LeftStickX);
        Assert.Equal(GamepadState.Neutral, registry.EffectiveState(2));
        Assert.False(registry.ShouldSuppressPhysical(new PhysicalInput("key:W", PhysicalInputType.KeyDown)));
        registry.Lifecycle(1, "pause");
        Assert.Equal(GamepadState.Neutral, registry.EffectiveState(1));
        Assert.Throws<InvalidOperationException>(() => registry.HandleProgram("program.state", Payload(new { controller = 1, token, ttlMs = 100, state = GamepadState.Neutral })));
    }

    [Fact]
    public void MappingAndProgramCannotCompeteAndEmergencyRevokesBoth()
    {
        var registry = ControllerRegistry.CreateDefault(new NullXInputBackend());
        registry.Lifecycle(1, "start");
        Assert.Throws<InvalidOperationException>(() => registry.HandleProgram("program.acquire", Payload(new { controller = 1 })));
        registry.Lifecycle(1, "pause");
        registry.HandleProgram("program.acquire", Payload(new { controller = 1 }));
        Assert.Throws<InvalidOperationException>(() => registry.ExecuteLocal(1, s => s.Store.SetState("legacy", GamepadState.Neutral)));
        registry.EmergencyResetAll();
        registry.HandleProgram("program.acquire", Payload(new { controller = 1 }));
    }
}
