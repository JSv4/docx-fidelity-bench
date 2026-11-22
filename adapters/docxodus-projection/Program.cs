using System.Text.Json;
using System.Diagnostics;
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
    string? fullDate = null;
    if (operation == "date-fill")
    {
        bytes = FillDate(bytes, request.RootElement);
        using var savedStream = new MemoryStream(bytes);
        using var saved = WordprocessingDocument.Open(savedStream, false);
        fullDate = (string?)saved.MainDocumentPart!.GetXDocument().Descendants(W.date).Single().Attribute(W.fullDate);
    }
    using var session = new DocxSession(bytes, new DocxSessionSettings
    {
        ProjectionSettings = new WmlToMarkdownConverterSettings
        {
            TableMode = Enum.Parse<TableRenderMode>(request.RootElement.GetProperty("tableMode").GetString()!),
        },
    });
    object? raw = null;
    object? table = null;
    Dictionary<string, string?>? labels = null;
    if (operation == "list-labels")
    {
        var items = session.Project().AnchorIndex.Values.Where(a => a.Anchor.Kind == "li").ToArray();
        var metadata = session.GetBlockMetadatas(items.Select(a => a.Anchor.Id).ToArray());
        labels = items.ToDictionary(a => a.TextPreview, a => metadata[a.Anchor.Id]?.List?.GeneratedLabel);
    }
    else if (operation == "table-insert")
    {
        session.SetTrackedChanges(request.RootElement.GetProperty("tracked").GetBoolean()
            ? TrackedChangeMode.RenderInline : TrackedChangeMode.Accept);
        var anchorText = request.RootElement.GetProperty("anchor").GetString();
        var anchor = session.Project().AnchorIndex.Values.First(a => a.Anchor.Kind == "p" && a.TextPreview == anchorText).Anchor.Id;
        var edit = session.InsertTable(anchor, Position.After, 1, 1, new TableInsertOptions { CellContents = new[] { "LarchNew" } });
        var revisionCount = session.ListRevisions().Count;
        var inserted = session.Save();
        string Resolve(bool accept)
        {
            using var copy = new DocxSession(inserted);
            var resolution = accept ? copy.AcceptAllRevisions() : copy.RejectAllRevisions();
            if (!resolution.Success) throw new InvalidOperationException("Revision resolution failed");
            return copy.Project().Markdown;
        }
        var undo = session.Undo();
        if (undo && !session.Redo()) throw new InvalidOperationException("Redo failed");
        table = new { success = edit.Success, error = edit.Error?.Code.ToString(), revisionCount,
            accepted = Resolve(true), rejected = Resolve(false), undo };
    }
    else if (operation is not null and not "date-fill")
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
        path, errors, raw, table, fullDate, labels, markdown = projection.Markdown,
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

// Exercise the shipped string parser in a dedicated east-of-UTC host.
static byte[] FillDate(byte[] bytes, JsonElement request)
{
    var start = new ProcessStartInfo(Environment.ProcessPath!)
    {
        UseShellExecute = false, RedirectStandardInput = true, RedirectStandardOutput = true,
    };
    start.ArgumentList.Add(Path.Combine(AppContext.BaseDirectory, "docxodus-pyhost.dll"));
    start.Environment["TZ"] = "Asia/Tokyo";
    using var host = Process.Start(start) ?? throw new InvalidOperationException("Could not start date host");
    long id = 0;
    JsonElement Call(string op, object args)
    {
        host.StandardInput.WriteLine(JsonSerializer.Serialize(new { id = ++id, op, args }));
        host.StandardInput.Flush();
        var line = host.StandardOutput.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(20)).GetAwaiter().GetResult();
        using var reply = JsonDocument.Parse(line ?? throw new EndOfStreamException(op));
        var envelope = reply.RootElement;
        if (envelope.GetProperty("id").GetInt64() != id || !envelope.GetProperty("ok").GetBoolean())
            throw new InvalidDataException($"Date host failed {op}: {envelope}");
        return envelope.GetProperty("result").Clone();
    }
    try
    {
        var handle = Call("open_session", new { docxB64 = Convert.ToBase64String(bytes) }).GetInt32();
        var anchorId = Call("list_content_controls", new { handle }).EnumerateArray().Single().GetProperty("anchorId").GetString();
        var edit = Call("set_content_control_date", new { handle, anchorId, value = request.GetProperty("value"),
            displayText = request.GetProperty("display") });
        if (!edit.GetProperty("success").GetBoolean()) throw new InvalidDataException($"Date fill failed: {edit}");
        return Call("save", new { handle }).GetProperty("docxB64").GetBytesFromBase64();
    }
    finally
    {
        host.StandardInput.Close();
        if (!host.WaitForExit(5000)) host.Kill(entireProcessTree: true);
    }
}
