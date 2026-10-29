using System.IO.Compression;
using System.Net;
using System.Text.Json;
using System.Xml.Linq;
using Docxodus;

var input = Path.GetFullPath(args[0]);
var output = Path.GetFullPath(args[1]);
Directory.CreateDirectory(output);
var records = new List<object>();
foreach (var folder in Directory.GetDirectories(input).Order())
{
    var source = Path.Combine(folder, "candidate-redline.docx");
    if (!File.Exists(source)) continue;
    var name = Path.GetFileName(folder);
    var atoms = "";
    foreach (var accept in new[] { true, false })
    {
        using var session = new DocxSession(File.ReadAllBytes(source));
        var edit = accept ? session.AcceptAllRevisions() : session.RejectAllRevisions();
        if (!edit.Success) throw new Exception(edit.Error?.Message);
        var bytes = session.Save();
        var mode = accept ? "accepted" : "rejected";
        var html = WmlToHtmlConverter.ConvertToHtml(new WmlDocument(name + ".docx", bytes), new());
        File.WriteAllText(Path.Combine(output, name + "-" + mode + ".html"), html.ToString(SaveOptions.DisableFormatting));
        if (!accept)
        {
            using var zip = new ZipArchive(new MemoryStream(bytes));
            using var stream = zip.GetEntry("word/document.xml")!.Open();
            XNamespace w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
            var names = new HashSet<string> { "tab", "ptab", "br", "cr", "sym", "noBreakHyphen", "softHyphen" };
            atoms = string.Join("; ", XDocument.Load(stream).Descendants(w + "r").SelectMany(r => r.Elements())
                .Where(e => names.Contains(e.Name.LocalName)).Select(e => e.Name.LocalName + " " +
                    string.Join(" ", e.Attributes().Where(a => a.Name.Namespace == w).Select(a => a.Name.LocalName + "=" + a.Value))));
        }
        records.Add(new { name, mode, sha256 = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(bytes)).ToLowerInvariant() });
    }
    var title = WebUtility.HtmlEncode(name);
    File.WriteAllText(Path.Combine(output, name + ".html"), "<!doctype html><meta charset=utf-8>" +
        "<style>body{font:14px sans-serif;margin:24px;background:#f5f7fa;color:#182334}h1{font-size:18px}" +
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}iframe{width:100%;height:290px;border:1px solid #b7c4d4;background:white}" +
        "pre{white-space:pre-wrap;font-size:12px}h2{font-size:16px}</style><h1>" + title + "</h1>" +
        "<p>Docxodus d318fbb3 — public native revision resolution, then native flow HTML</p>" +
        "<div class=grid><section><h2>Accept</h2><iframe src='" + name + "-accepted.html'></iframe></section>" +
        "<section><h2>Reject</h2><iframe src='" + name + "-rejected.html'></iframe></section></div>" +
        "<h2>Restored native run atoms</h2><pre>" + WebUtility.HtmlEncode(atoms.Length == 0 ? "None (ordinary text control)" : atoms) +
        "</pre><p>Review preview only. Positional tabs and page/column layout are approximate here; this is not a Word reference or PDF score.</p>");
}
File.WriteAllText(Path.Combine(output, "resolved-hashes.json"), JsonSerializer.Serialize(records, new JsonSerializerOptions { WriteIndented = true }));
