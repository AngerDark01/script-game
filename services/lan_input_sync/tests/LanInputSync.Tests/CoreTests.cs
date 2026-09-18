using System.Security.Cryptography;

namespace LanInputSync.Tests;

public class CoreTests
{
    [Fact]
    public void AuthenticationRejectsTamperingReplayAndAnotherSession()
    {
        byte[] a = RandomNumberGenerator.GetBytes(32), b = RandomNumberGenerator.GetBytes(32);
        Guid id = Guid.NewGuid();
        using var sender = new SecurePackets(id, a, b);
        using var receiver = new SecurePackets(id, b, a);
        using var stranger = new SecurePackets(Guid.NewGuid(), b, a);
        byte[] packet = sender.Encode(0, [1, 2, 3]);
        byte[] corrupt = packet.ToArray(); corrupt[^1] ^= 1;
        Assert.False(receiver.TryDecode(corrupt, out _, out _));
        Assert.False(stranger.TryDecode(packet, out _, out _));
        Assert.True(receiver.TryDecode(packet, out byte lane, out var payload));
        Assert.Equal(0, lane); Assert.Equal(new byte[] { 1, 2, 3 }, payload);
        Assert.False(receiver.TryDecode(packet, out _, out _));
    }
    [Fact]
    public void LatestSnapshotCannotSuppressReliableButtonChangesAcrossLanes()
    {
        var slot = new ReceiverSlot();
        slot.Snapshot(1, 2, true, new(LeftStickY: 20000), 100);
        Assert.True(slot.Transition(1, 1, true, 0x1000, 101));
        Assert.True(slot.Transition(1, 2, true, 0, 102));
        Assert.Equal(0x1000, slot.Consume().Buttons);
        Assert.Equal(0, slot.Consume().Buttons);
        Assert.Equal(20000, slot.Output.LeftStickY);
    }
    [Fact]
    public void PauseSnapshotInvalidatesDelayedDownAndOldEpoch()
    {
        var slot = new ReceiverSlot();
        Assert.True(slot.Transition(1, 1, true, 1, 100));
        slot.Snapshot(1, 1, true, new(1, LeftStickY: 20000), 101);
        Assert.Equal(1, slot.Consume().Buttons);
        slot.Snapshot(2, 2, false, PadState.Neutral, 110);
        Assert.True(slot.Transition(1, 1, true, 1, 111));
        Assert.Equal(PadState.Neutral, slot.Consume());
    }
    [Fact]
    public void NoSnapshotOrUndrainedButtonsExpireOnMonotonicDeadline()
    {
        var slot = new ReceiverSlot();
        slot.Transition(1, 1, true, 1, 100);
        slot.Snapshot(1, 1, true, new(1), 100);
        Assert.False(slot.IsExpired(299, 200)); Assert.True(slot.IsExpired(301, 200));
        slot.Snapshot(1, 1, true, new(1), 300);
        Assert.True(slot.IsExpired(301, 200));
        slot.Reset(); Assert.Equal(PadState.Neutral, slot.Consume());
    }
    [Fact]
    public void ButtonQueueHasHardBoundAndDetectsGaps()
    {
        var slot = new ReceiverSlot();
        Assert.True(slot.Transition(1, 1, true, 1, 100));
        Assert.False(slot.Transition(1, 3, true, 0, 100));
        for (uint r = 2; r <= 32; r++) Assert.True(slot.Transition(1, r, true, (ushort)(r % 2), 100));
        Assert.False(slot.Transition(1, 33, true, 1, 100));
    }
    [Fact]
    public void PacketLanesHaveIndependentReplayOrder()
    {
        byte[] a = RandomNumberGenerator.GetBytes(32), b = RandomNumberGenerator.GetBytes(32); Guid id = Guid.NewGuid();
        using var sender = new SecurePackets(id, a, b); using var receiver = new SecurePackets(id, b, a);
        byte[] buttons = sender.Encode(1, [5]);
        for (int i = 0; i < 20; i++) Assert.True(receiver.TryDecode(sender.Encode(0, [0]), out _, out _));
        Assert.True(receiver.TryDecode(buttons, out _, out _));
    }
    [Fact]
    public void OldEpochTrafficCannotRefreshFreshnessDeadline()
    {
        var slot = new ReceiverSlot();
        slot.Transition(3, 8, true, 0, 100); slot.Consume();
        slot.Snapshot(3, 8, true, new(LeftStickX: 123), 100);
        slot.Snapshot(2, 7, true, new(LeftStickX: -123), 300);
        Assert.Equal(100, slot.LastSnapshot);
        Assert.True(slot.IsExpired(301, 200));
    }
}
