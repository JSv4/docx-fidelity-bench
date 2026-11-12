using System.IO.Compression;
using System.Net;
using System.Security.Cryptography;
using System.Text.Json;
using System.Xml.Linq;
using Docxodus;

// Args: baseline run, candidate run, HTML directory, baseline commit, candidate commit.
var destination = Path.GetFullPath(args[2]);
Directory.CreateDirectory(destination);
var records = new List<object>();
string Encode(string value) => WebUtility.HtmlEncode(value);
string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
foreach (var folder in Directory.GetDirectories(args[1]).Order())
{
    var name = Path.GetFileName(folder);
    if (!File.Exists(Path.Combine(folder, "candidate-redline.docx"))) continue;
    var sections = new List<string>();
    foreach (var (run, commit, label) in new[] { (args[0], args[3], "Before"), (args[1], args[4], "After") })
    {
        var bytes = File.ReadAllBytes(Path.Combine(run, name, "candidate-redline.docx"));
        var html = WmlToHtmlConverter.ConvertToHtml(new WmlDocument(name + ".docx", bytes), new());
        var filename = name + "-" + label.ToLowerInvariant() + ".html";
        File.WriteAllText(Path.Combine(destination, filename), html.ToString(SaveOptions.DisableFormatting));
        using var zip = new ZipArchive(new MemoryStream(bytes));
        using var input = zip.GetEntry("word/document.xml")!.Open();
        XNamespace w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
        var controls = XDocument.Load(input).Descendants(w + "sdt").Select(e => new XElement(e)).ToArray();
        foreach (var control in controls)
            control.DescendantsAndSelf().Attributes().Where(a => a.Name.NamespaceName == "http://powertools.codeplex.com/2011").Remove();
        var metadata = controls.Length == 0 ? "No native content control" : string.Join("\n", controls.Select(e => e.ToString()));
        sections.Add("<section><h2>" + label + " operation: " + Encode(commit[..8]) + "</h2><iframe src='" + filename +
            "'></iframe><h3>Saved native controls (" + controls.Length + ")</h3><pre>" + Encode(metadata) + "</pre></section>");
        records.Add(new { name, label, commit, outputSha256 = Hash(bytes), controlCount = controls.Length });
    }
    File.WriteAllText(Path.Combine(destination, name + ".html"), "<!doctype html><meta charset=utf-8>" +
        "<style>body{font:14px sans-serif;margin:24px;background:#f5f7fa;color:#182334}h1{font-size:18px}" +
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}iframe{width:100%;height:160px;border:1px solid #b7c4d4;background:white}" +
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:white;padding:12px}h2{font-size:16px}</style>" +
        "<h1>" + Encode(name) + "</h1><p>Public ReplaceText outputs. Native flow renderer " + Encode(args[4][..8]) +
        " for both previews. Native XML is shown below each saved output.</p><div class=grid>" + string.Join("", sections) +
        "</div><p>Review preview only; no Word reference or PDF score. Captured offline with installed fonts.</p>");
}
File.WriteAllText(Path.Combine(destination, "output-hashes.json"), JsonSerializer.Serialize(records, new JsonSerializerOptions { WriteIndented = true }));
