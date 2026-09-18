using AutoModules.Installer;

namespace Installer.Tests;

public sealed class RuntimeLayoutTests : IDisposable
{
    private readonly string _root = Path.Combine(Path.GetTempPath(), "AutoModules installer " + Guid.NewGuid());

    [Fact]
    public void SeedsDefaultsButNeverOverwritesConfigurationOrRestoresEditedMapFiles()
    {
        var source = Path.Combine(_root, "安装 defaults");
        var target = Path.Combine(_root, "用户 data");
        Directory.CreateDirectory(Path.Combine(source, "maps", "map1"));
        File.WriteAllText(Path.Combine(source, "config.json"), "defaults");
        File.WriteAllText(Path.Combine(source, "maps", "map1", "walls.npz"), "walls");
        RuntimeLayout.SeedDefaults(source, target);
        Assert.Equal("defaults", File.ReadAllText(Path.Combine(target, "config.json")));
        File.WriteAllText(Path.Combine(target, "config.json"), "user edits");
        File.Delete(Path.Combine(target, "maps", "map1", "walls.npz"));
        RuntimeLayout.SeedDefaults(source, target);
        Assert.Equal("user edits", File.ReadAllText(Path.Combine(target, "config.json")));
        Assert.False(File.Exists(Path.Combine(target, "maps", "map1", "walls.npz")));
    }

    public void Dispose() { if (Directory.Exists(_root)) Directory.Delete(_root, true); }

    [Fact]
    public void SeedsProfilesButDoesNotCopyPrivateIdentitiesOrOverwriteBindings()
    {
        var source = Path.Combine(_root, "defaults");
        var target = Path.Combine(_root, "data");
        Directory.CreateDirectory(Path.Combine(source, "virtual_gamepad", "configs"));
        Directory.CreateDirectory(Path.Combine(source, "pairing"));
        File.WriteAllText(Path.Combine(source, "pairing", "identity.key"), "never copy");
        var profile = Path.Combine("virtual_gamepad", "configs", "controller-1.json");
        File.WriteAllText(Path.Combine(source, profile), "default binding");
        RuntimeLayout.SeedDefaults(source, target);
        Assert.Equal("default binding", File.ReadAllText(Path.Combine(target, profile)));
        File.WriteAllText(Path.Combine(target, profile), "custom J binding");
        RuntimeLayout.SeedDefaults(source, target);
        Assert.Equal("custom J binding", File.ReadAllText(Path.Combine(target, profile)));
        Assert.False(Directory.Exists(Path.Combine(target, "pairing")));
    }

    [Fact]
    public void IncompletePayloadFailsWithActionableMissingFile()
    {
        var error = Assert.Throws<FileNotFoundException>(() => RuntimeLayout.ValidatePayload(_root));
        Assert.Contains("python/pythonw.exe", error.Message);
    }

    [Fact]
    public void FailedConfigurationCopyDoesNotLeavePartialDestination()
    {
        var source = Path.Combine(_root, "defaults");
        var target = Path.Combine(_root, "data");
        Directory.CreateDirectory(source);
        var config = Path.Combine(source, "config.json");
        File.WriteAllText(config, "{\"binding\":\"J\"}");
        using (var lockedSource = new FileStream(config, FileMode.Open, FileAccess.Read, FileShare.None))
        {
            Assert.Throws<IOException>(() => RuntimeLayout.SeedDefaults(source, target));
            Assert.False(File.Exists(Path.Combine(target, "config.json")));
            Assert.Empty(Directory.EnumerateFiles(target));
        }
        RuntimeLayout.SeedDefaults(source, target);
        Assert.Equal("{\"binding\":\"J\"}", File.ReadAllText(Path.Combine(target, "config.json")));
        Assert.Single(Directory.EnumerateFiles(target));
    }

    [Fact]
    public void LaunchUsesBundledRuntimeAbsolutePathsAndIsolatedEnvironment()
    {
        var root = Path.Combine(_root, "软件 install");
        var data = Path.Combine(_root, "我的 data");
        var start = RuntimeLayout.CreateStartInfo(root, data);
        Assert.Equal(Path.Combine(root, "python", "pythonw.exe"), start.FileName);
        Assert.Equal(new[] { "-I", "-B", Path.Combine(root, "app", "main.py") }, start.ArgumentList);
        Assert.Equal(data, start.WorkingDirectory);
        Assert.Equal(data, start.Environment["AUTO_MODULES_DATA_DIR"]);
        Assert.Equal(Path.Combine(root, "host"), start.Environment["AUTO_MODULES_HOST_DIR"]);
        Assert.Equal(Path.Combine(root, "app", "resources"), start.Environment["AUTO_MODULES_RESOURCE_DIR"]);
        Assert.False(start.Environment.ContainsKey("PYTHONHOME"));
        Assert.False(start.Environment.ContainsKey("PYTHONPATH"));
        Assert.False(start.Environment.ContainsKey("QT_QPA_PLATFORM"));
        Assert.Equal("1", start.Environment["PYTHONDONTWRITEBYTECODE"]);
        Assert.False(start.UseShellExecute);
    }
}
