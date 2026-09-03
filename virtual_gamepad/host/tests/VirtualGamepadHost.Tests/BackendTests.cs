using VirtualGamepadHost.Model;

namespace VirtualGamepadHost.Tests;

public sealed class BackendTests
{
    [Fact]
    public void BackendReceivesCompleteReportsAndDisconnects()
    {
        using var backend = new FakeXInputBackend();
        backend.Start();

        var expected = GamepadState.Neutral
            .WithButton(GamepadButton.A, true)
            .WithAxis(GamepadAxis.LeftY, 32767);
        backend.Submit(expected);
        backend.Stop();

        Assert.Equal(expected, Assert.Single(backend.Reports));
        Assert.False(backend.IsConnected);
    }
}
