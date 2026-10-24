// Original redline-track adapter: one JSON request on stdin, one JSON response on stdout.
// It calls only Docxodus's public comparison and revision APIs; the benchmark scores the output
// package with its own independent accept/reject engines.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using Docxodus;
using Docxodus.Verification;

namespace DocxBenchRedline;

internal static class Program
{
    private static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    private static int Main()
    {
        var phase = "setup";
        var response = new JsonObject { ["protocol"] = 1 };
        try
        {
            var request = JsonNode.Parse(Console.In.ReadToEnd()) as JsonObject ?? throw new InvalidDataException("Request must be a JSON object");
            if ((int?)request["protocol"] != 1)
                throw new InvalidDataException("Unknown request protocol");
            var operation = (string?)request["operation"] ?? throw new InvalidDataException("Missing operation");
            var output = (string?)request["output"] ?? throw new InvalidDataException("Missing output");
            var settings = request["settings"] as JsonObject ?? new JsonObject();
            var author = (string?)settings["author"] ?? "Bench";
            var date = (string?)settings["date"] ?? "2026-01-01T00:00:00Z";
            var documents = new List<(WmlDocument Document, string? Author)>();
            foreach (var item in request["inputs"] as JsonArray ?? throw new InvalidDataException("Missing inputs"))
            {
                var path = (string?)item?["path"] ?? throw new InvalidDataException("Missing input path");
                var bytes = File.ReadAllBytes(path);
                if (Hash(bytes) != (string?)item?["sha256"])
                    throw new InvalidDataException("Input digest mismatch: " + path);
                documents.Add((new WmlDocument(Path.GetFileName(path), bytes), (string?)item?["author"]));
            }
            phase = "operation";
            if (settings["semanticPreflight"] is not null)
            {
                if (operation != "compare" || documents.Count != 2 ||
                    settings["semanticPreflight"] is not JsonObject guard || guard.Count != 3 ||
                    (int?)guard["version"] != 1 || (string?)guard["limits"] != "raw-boundaries" ||
                    (int?)guard["changeCount"] != 0 ||
                    Hash(documents[0].Document.DocumentByteArray) != Hash(documents[1].Document.DocumentByteArray))
                    throw new InvalidDataException("Unsupported semantic preflight declaration");
                using var stream = new MemoryStream(documents[0].Document.DocumentByteArray);
                using var zip = new ZipArchive(stream, ZipArchiveMode.Read);
                var entries = zip.Entries.ToArray();
                var limits = new PackageManifestOptions
                {
                    MaxXmlPartBytes = entries.Max(e => e.Length),
                    MaxEntryUncompressedBytes = entries.Max(e => e.Length),
                    MaxTotalUncompressedBytes = entries.Sum(e => e.Length),
                    MaxCompressionRatio = entries.Max(e => (double)e.Length / e.CompressedLength),
                };
                var counts = new JsonObject();
                foreach (var include in new[] { true, false })
                    counts[include ? "withPackageChanges" : "withoutPackageChanges"] = SemanticDiff.Compare(
                        documents[0].Document.DocumentByteArray, documents[1].Document.DocumentByteArray,
                        new SemanticDiffOptions { IncludePackageChanges = include, PackageOptions = limits }).ChangeCount;
                response["semanticPreflight"] = counts;
            }
            WmlDocument result;
            var diff = new DocxDiffSettings { AuthorForRevisions = author, DateTimeForRevisions = date };
            switch (operation)
            {
                case "revision-ownership" when documents.Count == 1:
                {
                    var spec = settings["revisionOwnership"] as JsonObject ?? throw new InvalidDataException("Missing ownership edit");
                    if ((int?)spec["version"] != 1) throw new InvalidDataException("Unknown ownership version");
                    var actor = (string?)spec["author"] ?? throw new InvalidDataException("Missing reviewer name");
                    var sessionSettings = new DocxSessionSettings { RevisionAuthor = actor, TrackedChanges = TrackedChangeMode.RenderInline };
                    // Reflection binds only the new public account DTO/API. It keeps this adapter
                    // compilable against pre-feature candidates; missing support is a measured
                    // operation failure, never a build failure or name-based emulation.
                    Array? identities = null;
                    if (spec["identities"] is JsonArray records)
                    {
                        var property = typeof(DocxSessionSettings).GetProperty("RevisionIdentities")
                            ?? throw new NotSupportedException("Candidate has no revision identity setting");
                        var itemType = property.PropertyType.GetGenericArguments().Single();
                        identities = Array.CreateInstance(itemType, records.Count);
                        for (var i = 0; i < records.Count; i++)
                            identities.SetValue(Activator.CreateInstance(itemType,
                                (string?)records[i]?["providerId"], (string?)records[i]?["userId"]), i);
                        if ((string?)spec["configure"] == "open") property.SetValue(sessionSettings, identities);
                    }
                    using var session = new DocxSession(documents[0].Document.DocumentByteArray, sessionSettings);
                    if ((string?)spec["configure"] == "operation")
                    {
                        var setter = typeof(DocxSession).GetMethod("SetRevisionIdentities")
                            ?? throw new NotSupportedException("Candidate has no revision identity configuration operation");
                        setter.Invoke(session, new object?[] { identities });
                    }
                    var queryAuthor = (string?)spec["queryAuthor"];
                    JsonObject QueryName()
                    {
                        var query = typeof(DocxSession).GetMethod("GetRevisionAuthorNameStatus")
                            ?? throw new NotSupportedException("Candidate has no reviewer name status query");
                        return new JsonObject { ["author"] = queryAuthor,
                            ["status"] = query.Invoke(session, new object?[] { queryAuthor })?.ToString()?.ToLowerInvariant() };
                    }
                    var before = queryAuthor is null ? null : QueryName();
                    var paragraphs = session.Project().AnchorIndex.Values.Where(a => a.Anchor.Scope == "body" && a.Anchor.Kind == "p").ToArray();
                    var index = (int?)spec["paragraphIndex"] ?? throw new InvalidDataException("Missing paragraph index");
                    var anchor = paragraphs[index].Anchor.Id;
                    var text = (string?)spec["text"] ?? "";
                    var edit = (string?)spec["action"] switch
                    {
                        "delete-block" => session.DeleteBlock(anchor),
                        "replace-text" => session.ReplaceText(anchor, text),
                        "add-comment" => session.AddComment(anchor, null, actor, text, date: DateTime.Parse(date, null, System.Globalization.DateTimeStyles.AdjustToUniversal)),
                        _ => throw new InvalidDataException("Unknown ownership edit action"),
                    };
                    if (!edit.Success) throw new InvalidOperationException(edit.Error?.Message ?? "Ownership edit failed");
                    if (queryAuthor is not null)
                        response["revisionAuthorNameStatus"] = new JsonObject { ["before"] = before, ["after"] = QueryName() };
                    result = new WmlDocument("revision-ownership.docx", session.Save());
                    break;
                }
                case "replace-span" when documents.Count == 1:
                {
                    var spec = settings["spanEdit"] as JsonObject ?? throw new InvalidDataException("Missing span edit");
                    if ((int?)spec["version"] != 1) throw new InvalidDataException("Unknown span edit version");
                    using var session = new DocxSession(documents[0].Document.DocumentByteArray, new DocxSessionSettings
                    {
                        RevisionAuthor = author,
                        TrackedChanges = (bool?)spec["tracked"] == true ? TrackedChangeMode.RenderInline : TrackedChangeMode.Accept,
                    });
                    var paragraphs = session.Project().AnchorIndex.Values
                        .Where(a => a.Anchor.Scope == "body" && a.Anchor.Kind == "p").ToArray();
                    var index = (int?)spec["paragraphIndex"] ?? throw new InvalidDataException("Missing paragraph index");
                    var edit = session.ReplaceTextAtSpan(paragraphs[index].Anchor.Id,
                        (int?)spec["start"] ?? throw new InvalidDataException("Missing span start"),
                        (int?)spec["length"] ?? throw new InvalidDataException("Missing span length"),
                        (string?)spec["replacement"] ?? throw new InvalidDataException("Missing replacement"));
                    if (!edit.Success) throw new InvalidOperationException(edit.Error?.Message ?? "Span replacement failed");
                    result = new WmlDocument("span-edit.docx", session.Save());
                    break;
                }
                case "block-insert" when documents.Count == 1:
                {
                    var spec = settings["blockInsert"] as JsonObject ?? throw new InvalidDataException("Missing block insertion");
                    if ((int?)spec["version"] != 1) throw new InvalidDataException("Unknown block insertion version");
                    using var session = new DocxSession(documents[0].Document.DocumentByteArray);
                    var kind = (string?)spec["anchorKind"];
                    var anchor = session.Project().AnchorIndex.Values.First(a => a.Anchor.Scope == "body" && a.Anchor.Kind == kind).Anchor.Id;
                    var position = (string?)spec["position"] == "before" ? Position.Before : Position.After;
                    var version = session.Version;
                    var edit = (string?)spec["operation"] switch
                    {
                        "paragraph" => session.InsertParagraph(anchor, position, (string?)spec["markdown"] ?? ""),
                        "rule" => session.InsertHorizontalRule(anchor, position),
                        "table" => session.InsertTable(anchor, position, 1, 1),
                        _ => throw new InvalidDataException("Unknown block insertion operation"),
                    };
                    result = new WmlDocument("block-insert.docx", session.Save());
                    response["blockInsertion"] = new JsonObject
                    {
                        ["success"] = edit.Success,
                        ["errorCode"] = edit.Error?.Code.ToString(),
                        ["versionDelta"] = session.Version - version,
                        ["undoAvailable"] = session.Undo(),
                    };
                    break;
                }
                case "column-edit" when documents.Count == 1:
                {
                    var spec = settings["columnEdit"] as JsonObject ?? throw new InvalidDataException("Missing column edit");
                    var version = (int?)spec["version"];
                    if (version is not (1 or 2)) throw new InvalidDataException("Unknown column edit version");
                    using var session = version == 2
                        ? new DocxSession(documents[0].Document.DocumentByteArray, new DocxSessionSettings
                        {
                            RevisionAuthor = author,
                            TrackedChanges = (bool?)spec["tracked"] == true ? TrackedChangeMode.RenderInline : TrackedChangeMode.Accept,
                        })
                        : new DocxSession(documents[0].Document.DocumentByteArray);
                    var index = (int?)spec["cellIndex"] ?? throw new InvalidDataException("Missing cell index");
                    var cells = session.Project().AnchorIndex.Values.Where(a => a.Anchor.Scope == "body" && a.Anchor.Kind == "tc").ToArray();
                    var action = (string?)spec["action"];
                    var edit = action == "insert" ? session.InsertTableColumn(cells[index].Anchor.Id,
                        (string?)spec["position"] == "before" ? Position.Before : Position.After)
                        : action == "delete" ? session.DeleteTableColumn(cells[index].Anchor.Id)
                        : throw new InvalidDataException("Unknown column action");
                    if (!edit.Success) throw new InvalidOperationException(edit.Error?.Message ?? "Column edit failed");
                    var before = session.ListRevisions();
                    var review = new JsonObject
                    {
                        ["beforeCount"] = before.Count,
                        ["supported"] = before.All(revision => revision.ResolutionStatus == RevisionResolutionStatus.Supported),
                    };
                    bool resolutionSuccess = true;
                    if ((string?)spec["resolution"] == "reject-each")
                    {
                        var attempts = 0;
                        while (session.ListRevisions().FirstOrDefault() is { } revision)
                        {
                            if (++attempts > 1000) throw new InvalidOperationException("Revision resolution did not finish");
                            var resolved = session.RejectRevision(revision.Id);
                            if (!resolved.Success)
                            {
                                if (version == 1) throw new InvalidOperationException(resolved.Error?.Message ?? "Reject failed");
                                resolutionSuccess = false;
                                break;
                            }
                        }
                    }
                    else
                    {
                        var resolved = (string?)spec["resolution"] switch
                        {
                            "reject-all" => session.RejectAllRevisions(),
                            "accept-all" => session.AcceptAllRevisions(),
                            _ => throw new InvalidDataException("Unknown column resolution"),
                        };
                        resolutionSuccess = resolved.Success;
                        if (version == 1 && !resolved.Success) throw new InvalidOperationException(resolved.Error?.Message ?? "Resolution failed");
                    }
                    if (version == 2)
                    {
                        review["resolutionSuccess"] = resolutionSuccess;
                        response["columnReview"] = review;
                    }
                    response["revisionRegistryCount"] = session.ListRevisions().Count;
                    result = new WmlDocument("column-edit.docx", session.Save());
                    break;
                }
                case "table-widths" when documents.Count == 1:
                {
                    var spec = settings["tableWidths"] as JsonObject ?? throw new InvalidDataException("Missing table widths");
                    if ((int?)spec["version"] != 1) throw new InvalidDataException("Unknown table width version");
                    var widths = (spec["widths"] as JsonArray ?? throw new InvalidDataException("Missing widths"))
                        .Select(value => (int)value!).ToArray();
                    using var session = new DocxSession(documents[0].Document.DocumentByteArray, new DocxSessionSettings
                    {
                        RevisionAuthor = author,
                        TrackedChanges = (bool?)spec["tracked"] == true ? TrackedChangeMode.RenderInline : TrackedChangeMode.Accept,
                    });
                    var anchor = session.Project().AnchorIndex.Values.First(a => a.Anchor.Scope == "body" && a.Anchor.Kind == "tc").Anchor.Id;
                    var edit = session.SetColumnWidths(anchor, widths);
                    if (!edit.Success) throw new InvalidOperationException(edit.Error?.Message ?? "Column width operation failed");
                    response["revisionRegistryCount"] = session.ListRevisions().Count;
                    result = new WmlDocument("column-widths.docx", session.Save());
                    break;
                }
                case "build" when documents.Count >= 2:
                    result = DocumentBuilder.BuildDocument(documents.ConvertAll(d => new Source(d.Document, false)));
                    break;
                case "compare" when documents.Count == 2:
                    result = DocxCompare.Compare(documents[0].Document, documents[1].Document, diff);
                    break;
                case "consolidate" when documents.Count >= 2:
                    var reviewers = new List<DocxDiffReviewer>();
                    for (var i = 1; i < documents.Count; i++)
                        reviewers.Add(new DocxDiffReviewer { Document = documents[i].Document, Author = documents[i].Author ?? "Reviewer" + i });
                    result = DocxCompare.Consolidate(documents[0].Document, reviewers, new DocxDiffConsolidateSettings { Diff = diff });
                    break;
                case "reject" when documents.Count == 1:
                    result = RevisionProcessor.RejectRevisions(documents[0].Document);
                    break;
                case "accept" when documents.Count == 1:
                    result = RevisionProcessor.AcceptRevisions(documents[0].Document);
                    break;
                default:
                    phase = "setup";
                    throw new InvalidDataException("Unsupported operation or input count: " + operation);
            }
            phase = "artifact";
            var produced = result.DocumentByteArray;
            using (var stream = new FileStream(output, FileMode.CreateNew, FileAccess.Write))
                stream.Write(produced, 0, produced.Length);
            var assembly = typeof(DocxCompare).Assembly;
            response["status"] = "ok";
            response["outputSha256"] = Hash(produced);
            response["engine"] = new JsonObject
            {
                ["name"] = "docxodus",
                ["assembly"] = assembly.GetName().Name,
                ["informationalVersion"] = assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion,
                ["runtime"] = Environment.Version.ToString(),
            };
        }
        catch (Exception error)
        {
            response["status"] = phase == "operation" ? "failed" : "unmeasured";
            response["error"] = new JsonObject { ["phase"] = phase, ["type"] = error.GetType().FullName, ["message"] = error.Message };
        }
        Console.Out.Write(response.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
        return 0;
    }
}
