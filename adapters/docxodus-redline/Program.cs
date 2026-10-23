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
