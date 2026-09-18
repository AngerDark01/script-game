using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using Nefarius.ViGEm.Client;
using Nefarius.ViGEm.Client.Exceptions;
using Nefarius.ViGEm.Client.Targets;

namespace AutoModules.Installer;

public static class DriverInstaller
{
    public const string FileName = "ViGEmBus_1.22.0_x64_x86_arm64.exe";
    public const string ExpectedSha256 = "89220A7865076B342892F98865F3499FB7C4CFD673159E89D352C360FD014C6A";
    public const string ExpectedSigner = "Nefarius Software Solutions e.U.";

    public static int Check(Action<string> log, bool createController = false)
    {
        try
        {
            using var client = new ViGEmClient();
            if (createController)
            {
                var pad = (IVirtualGamepad)client.CreateXbox360Controller();
                try { pad.Connect(); log("Neutral Xbox controller creation succeeded."); }
                finally { pad.Disconnect(); }
            }
            log("ViGEmBus connection succeeded.");
            return DriverPolicy.Ready;
        }
        catch (VigemBusNotFoundException ex) { log("ViGEmBus is absent: " + ex.Message); return DriverPolicy.Missing; }
        catch (Exception ex) { log("ViGEmBus probe failed: " + ex); return DriverPolicy.ProbeFailed; }
    }

    public static int Ensure(string root, string logDirectory, Action<string> log)
    {
        var existing = Check(log);
        if (existing == DriverPolicy.Ready) return Check(log, createController: true);
        // A broken/incompatible driver is not the same as an absent driver: never downgrade/reinstall blindly.
        if (existing != DriverPolicy.Missing) return existing;
        var installer = Path.Combine(root, "prerequisites", FileName);
        FileStream lockedPrerequisite;
        try
        {
            // Keep the exact verified file locked against replacement until execution finishes.
            lockedPrerequisite = new FileStream(installer, FileMode.Open, FileAccess.Read, FileShare.Read);
            try { VerifyPrerequisite(installer); }
            catch { lockedPrerequisite.Dispose(); throw; }
        }
        catch (Exception ex) { log("Driver verification failed: " + ex); return DriverPolicy.VerificationFailed; }
        using var prerequisiteLock = lockedPrerequisite;
        var start = new ProcessStartInfo(installer) { UseShellExecute = false, CreateNoWindow = true };
        start.ArgumentList.Add("/quiet");
        start.ArgumentList.Add("/norestart");
        start.ArgumentList.Add("/log");
        start.ArgumentList.Add(Path.Combine(logDirectory, "vigembus-install.log"));
        try
        {
            using var process = Process.Start(start) ?? throw new IOException("Unable to start official ViGEmBus installer.");
            process.WaitForExit();
            log("Official ViGEmBus installer exit code: " + process.ExitCode);
            if (process.ExitCode != 0) return DriverPolicy.ClassifyResult(process.ExitCode, false);
            return DriverPolicy.ClassifyResult(0, Check(log, createController: true) == DriverPolicy.Ready);
        }
        catch (Exception ex) { log("Driver installation failed: " + ex); return DriverPolicy.InstallationFailed; }
    }

    public static void VerifyPrerequisite(string path)
    {
        using (var stream = File.OpenRead(path))
            if (!Convert.ToHexString(SHA256.HashData(stream)).Equals(ExpectedSha256, StringComparison.OrdinalIgnoreCase))
                throw new CryptographicException("Driver SHA-256 does not match the pinned official release.");
        Authenticode.Verify(path);
        using var certificate = new X509Certificate2(X509Certificate.CreateFromSignedFile(path));
        if (!string.Equals(certificate.GetNameInfo(X509NameType.SimpleName, false), ExpectedSigner, StringComparison.Ordinal))
            throw new CryptographicException("Driver publisher does not match Nefarius.");
    }
}

internal static class Authenticode
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct FileInfo
    { public uint Size; [MarshalAs(UnmanagedType.LPWStr)] public string Path; public IntPtr File; public IntPtr KnownSubject; }

    [StructLayout(LayoutKind.Sequential)]
    private struct TrustData
    {
        public uint Size; public IntPtr PolicyCallbackData; public IntPtr SipClientData;
        public uint UiChoice; public uint RevocationChecks; public uint UnionChoice; public IntPtr File;
        public uint StateAction; public IntPtr StateData; public IntPtr UrlReference; public uint ProviderFlags;
        public uint UiContext; public IntPtr SignatureSettings;
    }

    [DllImport("wintrust.dll", ExactSpelling = true, PreserveSig = true)]
    private static extern int WinVerifyTrust(IntPtr window, ref Guid action, ref TrustData data);

    public static void Verify(string path)
    {
        var file = new FileInfo { Size = (uint)Marshal.SizeOf<FileInfo>(), Path = path };
        var ptr = Marshal.AllocHGlobal(Marshal.SizeOf<FileInfo>());
        Marshal.StructureToPtr(file, ptr, false);
        var action = new Guid("00AAC56B-CD44-11d0-8CC2-00C04FC295EE");
        var data = new TrustData
        {
            Size = (uint)Marshal.SizeOf<TrustData>(), UiChoice = 2, UnionChoice = 1, File = ptr,
            StateAction = 1, ProviderFlags = 0x1000 | 0x10 // cache-only retrieval, no online revocation; timestamp-aware chain verification remains enabled
        };
        try
        {
            var result = WinVerifyTrust(new IntPtr(-1), ref action, ref data);
            if (result != 0) throw new CryptographicException($"Driver Authenticode verification failed: 0x{result:X8}.");
        }
        finally
        {
            data.StateAction = 2;
            WinVerifyTrust(new IntPtr(-1), ref action, ref data);
            Marshal.DestroyStructure<FileInfo>(ptr);
            Marshal.FreeHGlobal(ptr);
        }
    }
}
