using System.Text.Json;
using System.IO.Compression;
using System.Security.Cryptography;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;
using Docxodus;

var outputs = args.Select(argument =>
{
    using var request = JsonDocument.Parse(argument);
    var path = request.RootElement.GetProperty("path").GetString()!;
    var operation = request.RootElement.GetProperty("operation").GetString();
    var bytes = File.ReadAllBytes(path);
    using var session = new DocxSession(bytes);
    object? raw = null;
    if (operation is not null)
    {
        session.SetTrackedChanges(request.RootElement.GetProperty("tracked").GetBoolean()
            ? TrackedChangeMode.RenderInline : TrackedChangeMode.Accept);
        var anchor = session.Project().AnchorIndex.Values.First(a => a.TextPreview == "LarchOriginal").Anchor.Id;
        var before = Parts(session.Save());
        var edit = operation switch
        {
            "raw-replace" => session.Raw.ReplaceXml(anchor,
                session.Raw.GetXml(anchor).Replace("LarchOriginal", "LarchReplacement")),
            "raw-insert" => session.Raw.InsertXml(anchor, Position.After,
                $"<w:p xmlns:w=\"{W.w}\"><w:r><w:t>LarchReplacement</w:t></w:r></w:p>"),
            _ => throw new ArgumentException("Unknown mutation: " + operation),
        };
        var unchanged = before.SequenceEqual(Parts(session.Save()));
        var revisionCount = session.ListRevisions().Count;
        var undo = session.Undo();
        if (undo && !session.Redo()) throw new InvalidOperationException("Redo failed");
        raw = new { success = edit.Success, error = edit.Error?.Code.ToString(), revisionCount, unchanged, undo };
    }
    using var stream = new MemoryStream(session.Save());
    using var package = WordprocessingDocument.Open(stream, false);
    var errors = new OpenXmlValidator(FileFormatVersions.Microsoft365).Validate(package)
        .Select(error => error.Description).ToArray();
    var projection = session.Project();
    return new
    {
        path, errors, raw, markdown = projection.Markdown,
        paragraphs = projection.AnchorIndex.Values.Where(a => a.Anchor.Kind == "p")
            .Select(a => new { id = a.Anchor.Id, text = a.TextPreview,
                markdown = session.ProjectAnchor(a.Anchor.Id, ProjectionDepth.SelfOnly).Markdown }).ToArray(),
    };
}).ToArray();
Console.WriteLine(JsonSerializer.Serialize(outputs));

// Compare every uncompressed part, independent of ZIP metadata and entry ordering.
static string[] Parts(byte[] bytes)
{
    using var stream = new MemoryStream(bytes);
    using var zip = new ZipArchive(stream);
    return zip.Entries.OrderBy(e => e.FullName).Select(e =>
    {
        using var content = e.Open();
        return e.FullName + ":" + Convert.ToHexString(SHA256.HashData(content));
    }).ToArray();
}
