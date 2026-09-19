namespace LanInputSync.Tests;

public sealed class TrustStoreTests
{
    [Fact]
    public void TrustStorePersistsMetadataAndRejectsChangedCertificate()
    {
        string directory = Path.Combine(Path.GetTempPath(), "lan-trust-" + Guid.NewGuid().ToString("N"));
        try
        {
            var store = new PeerTrustStore(directory);
            store.Save(new("peer-a", "device-a", "fingerprint-a", "A", "127.0.0.1", 45873, 1));
            Assert.Equal("fingerprint-a", store.Get("peer-a")!.CertificateFingerprint);
            Assert.Throws<AuthenticationException>(() => store.Save(new("peer-a", "device-a", "fingerprint-b", "A", "127.0.0.1", 45873)));
            store.Revoke("peer-a");
            Assert.True(store.IsRevoked("peer-a"));
            store.Forget("peer-a");
            Assert.Null(store.Get("peer-a"));
            Assert.False(store.IsRevoked("peer-a"));
        }
        finally { if (Directory.Exists(directory)) Directory.Delete(directory, true); }
    }

    [Fact]
    public void ReconnectBackoffIsBoundedAndResettable()
    {
        var backoff = new ReconnectBackoff();
        Assert.Equal(TimeSpan.FromSeconds(1), backoff.Next("peer"));
        Assert.Equal(TimeSpan.FromSeconds(2), backoff.Next("peer"));
        for (int i = 0; i < 10; i++) Assert.Equal(TimeSpan.FromSeconds(30), backoff.Next("peer"));
        backoff.Reset("peer");
        Assert.Equal(TimeSpan.FromSeconds(1), backoff.Next("peer"));
    }

    [Fact]
    public void CapabilitySetMapsLegacyDataSessionAndRejectsUnknownNames()
    {
        Assert.True(SessionCapabilities.Allows(SessionCapabilities.Legacy(true, false), SessionCapability.EventPublish));
        Assert.True(SessionCapabilities.Allows(SessionCapabilities.Legacy(false, true), SessionCapability.InputReceive));
        Assert.Throws<ArgumentException>(() => SessionCapabilities.Parse(["unknown.topic"]));
        Assert.Contains("map.subscribe", SessionCapabilities.ToWire(SessionCapability.MapSubscribe));
    }
}

