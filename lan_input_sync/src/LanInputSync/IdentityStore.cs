using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;

namespace LanInputSync;

internal sealed record TrustedPeer(string DeviceId, string Name, string Address, int Port, int[] Controllers);
internal sealed record Preferences(string Name, string BindAddress, int Port, int[] Controllers, int RateHz = 125);

internal sealed class IdentityStore : IDisposable
{
    private readonly string _directory;
    private readonly object _disk = new();
    public X509Certificate2 Certificate { get; }
    public string DeviceId { get; }
    public static string Fingerprint(X509Certificate certificate) => Convert.ToHexString(SHA256.HashData(certificate.GetRawCertData()));

    public IdentityStore(string? directory)
    {
        if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("Local device identity uses Windows DPAPI.");
        _directory = directory ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AutoModules", "LanInputSync");
        Directory.CreateDirectory(_directory);
        string file = Path.Combine(_directory, "identity.dpapi");
        if (File.Exists(file))
        {
            byte[] pfx = ProtectedData.Unprotect(File.ReadAllBytes(file), null, DataProtectionScope.CurrentUser);
            // Schannel needs a user key container. Without PersistKeySet, .NET deletes the
            // temporary imported container on disposal; only the DPAPI blob persists.
            try { Certificate = new X509Certificate2(pfx, (string?)null, X509KeyStorageFlags.UserKeySet); }
            finally { CryptographicOperations.ZeroMemory(pfx); }
        }
        else
        {
            using var key = RSA.Create(2048);
            var request = new CertificateRequest("CN=AutoModules LAN Input", key, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
            request.CertificateExtensions.Add(new X509KeyUsageExtension(X509KeyUsageFlags.DigitalSignature, true));
            using var generated = request.CreateSelfSigned(DateTimeOffset.UtcNow.AddDays(-1), DateTimeOffset.UtcNow.AddYears(10));
            byte[] pfx = generated.Export(X509ContentType.Pfx);
            try
            {
                Certificate = new X509Certificate2(pfx, (string?)null, X509KeyStorageFlags.UserKeySet);
                Atomic(file, ProtectedData.Protect(pfx, null, DataProtectionScope.CurrentUser));
            }
            finally { CryptographicOperations.ZeroMemory(pfx); }
        }
        DeviceId = Fingerprint(Certificate);
    }

    public T? Read<T>(string name)
    {
        lock (_disk)
        {
            var path = Path.Combine(_directory, name);
            return File.Exists(path) ? JsonSerializer.Deserialize<T>(File.ReadAllBytes(path)) : default;
        }
    }
    public void Write<T>(string name, T value)
    {
        lock (_disk) Atomic(Path.Combine(_directory, name), JsonSerializer.SerializeToUtf8Bytes(value));
    }
    private static void Atomic(string path, byte[] bytes)
    {
        string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        File.WriteAllBytes(temporary, bytes);
        File.Move(temporary, path, true);
    }
    public void Dispose() => Certificate.Dispose();
}
