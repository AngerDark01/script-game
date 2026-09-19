using System.Security.Authentication;
using System.Text.Json;

namespace LanInputSync;

internal sealed record PeerTrustRecord(
    string PeerId,
    string DeviceId,
    string CertificateFingerprint,
    string Name,
    string Address,
    int Port,
    long LastSeenUtcMs = 0);

/// <summary>Non-secret trust metadata. Session keys never enter this store.</summary>
internal sealed class PeerTrustStore
{
    private readonly string _path;
    private readonly string _revocationPath;
    private readonly object _gate = new();
    private Dictionary<string, PeerTrustRecord> _records;
    private HashSet<string> _revoked;

    public PeerTrustStore(string directory)
    {
        Directory.CreateDirectory(directory);
        _path = Path.Combine(directory, "trusted_peers.json");
        _revocationPath = Path.Combine(directory, "revocations.json");
        _records = Read<Dictionary<string, PeerTrustRecord>>(_path) ?? new();
        _revoked = Read<HashSet<string>>(_revocationPath) ?? new();
    }

    public PeerTrustRecord? Get(string peerId)
    {
        lock (_gate) return _records.GetValueOrDefault(peerId);
    }

    public IReadOnlyCollection<PeerTrustRecord> List()
    {
        lock (_gate) return _records.Values.ToArray();
    }

    public void Save(PeerTrustRecord record, bool replaceCertificate = false)
    {
        ArgumentException.ThrowIfNullOrEmpty(record.PeerId);
        ArgumentException.ThrowIfNullOrEmpty(record.CertificateFingerprint);
        if (record.Port is < 1 or > 65535) throw new ArgumentOutOfRangeException(nameof(record.Port));
        lock (_gate)
        {
            if (_records.TryGetValue(record.PeerId, out var existing)
                && !StringComparer.Ordinal.Equals(existing.CertificateFingerprint, record.CertificateFingerprint)
                && !replaceCertificate)
                throw new AuthenticationException($"Certificate fingerprint changed for {record.PeerId}");
            _records[record.PeerId] = record;
            AtomicWrite(_path, _records);
        }
    }

    public bool IsRevoked(string peerId)
    {
        lock (_gate) return _revoked.Contains(peerId);
    }

    public void Revoke(string peerId)
    {
        lock (_gate)
        {
            _revoked.Add(peerId);
            AtomicWrite(_revocationPath, _revoked);
        }
    }

    public void Forget(string peerId)
    {
        lock (_gate)
        {
            _records.Remove(peerId);
            _revoked.Remove(peerId);
            AtomicWrite(_path, _records);
            AtomicWrite(_revocationPath, _revoked);
        }
    }

    private static T? Read<T>(string path)
    {
        if (!File.Exists(path)) return default;
        try { return JsonSerializer.Deserialize<T>(File.ReadAllBytes(path)); }
        catch (Exception ex) when (ex is IOException or JsonException or NotSupportedException)
        { throw new InvalidDataException($"Invalid communication trust file: {path}", ex); }
    }

    private static void AtomicWrite<T>(string path, T value)
    {
        string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        File.WriteAllBytes(temporary, JsonSerializer.SerializeToUtf8Bytes(value));
        File.Move(temporary, path, true);
    }
}

internal sealed class ReconnectBackoff
{
    private static readonly TimeSpan[] Delays =
    [
        TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(2), TimeSpan.FromSeconds(5),
        TimeSpan.FromSeconds(15), TimeSpan.FromSeconds(30)
    ];
    private readonly Dictionary<string, int> _attempts = new();

    public TimeSpan Next(string peerId)
    {
        int attempt = _attempts.GetValueOrDefault(peerId);
        _attempts[peerId] = attempt + 1;
        return Delays[Math.Min(attempt, Delays.Length - 1)];
    }

    public void Reset(string peerId) => _attempts.Remove(peerId);
}
