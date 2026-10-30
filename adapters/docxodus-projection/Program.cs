using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;
using Docxodus;

var outputs = args.Select(path =>
{
    var bytes = File.ReadAllBytes(path);
    using var stream = new MemoryStream(bytes);
    using var package = WordprocessingDocument.Open(stream, false);
    var errors = new OpenXmlValidator(FileFormatVersions.Microsoft365).Validate(package)
        .Select(error => error.Description).ToArray();
    using var session = new DocxSession(bytes);
    var projection = session.Project();
    return new
    {
        path, errors, markdown = projection.Markdown,
        paragraphs = projection.AnchorIndex.Values.Where(a => a.Anchor.Kind == "p")
            .Select(a => new { id = a.Anchor.Id, text = a.TextPreview,
                markdown = session.ProjectAnchor(a.Anchor.Id, ProjectionDepth.SelfOnly).Markdown }).ToArray(),
    };
}).ToArray();
Console.WriteLine(JsonSerializer.Serialize(outputs));
