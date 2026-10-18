// Original redline-track validation tool: validates each named package with the pinned Open XML
// SDK and prints one JSON object mapping each path to its findings.
using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Nodes;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;

namespace OoxmlValidatorTool;

internal static class Program
{
    private const FileFormatVersions Format = FileFormatVersions.Microsoft365;

    private static int Main(string[] args)
    {
        var result = new JsonObject
        {
            ["fileFormat"] = Format.ToString(),
            ["sdk"] = typeof(OpenXmlValidator).Assembly.GetName().Version?.ToString(),
        };
        var documents = new JsonObject();
        foreach (var path in args)
        {
            var findings = new JsonArray();
            try
            {
                using var document = WordprocessingDocument.Open(path, false);
                foreach (var error in new OpenXmlValidator(Format).Validate(document))
                {
                    findings.Add(new JsonObject
                    {
                        ["id"] = error.Id,
                        ["type"] = error.ErrorType.ToString(),
                        ["part"] = error.Part?.Uri.ToString(),
                        ["path"] = error.Path?.XPath,
                        ["description"] = error.Description,
                    });
                }
            }
            catch (Exception exception)
            {
                findings.Add(new JsonObject { ["id"] = "Package_Open", ["type"] = "Package", ["part"] = null, ["path"] = null, ["description"] = exception.GetType().Name + ": " + exception.Message });
            }
            documents[path] = findings;
        }
        result["documents"] = documents;
        Console.Out.Write(result.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
        return 0;
    }
}
