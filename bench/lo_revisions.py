"""Accept or reject every tracked change with LibreOffice through headless UNO.

This file runs under LibreOffice's own Python (the interpreter that can import ``uno``), not under
the harness interpreter. It reads one JSON job on stdin and writes one JSON result on stdout. It
starts its own soffice process with a private profile and pipe, and terminates only that process.

Job: {"soffice": path, "profile": directory, "items": [{"input": path, "operation": "accept" |
"reject" | "load", "output": path}]}. Each output is the document saved by LibreOffice's
"MS Word 2007 XML" filter. Each result records the tracked-change count LibreOffice reports before
and after the operation, so a run can prove that the engine saw and resolved the revisions.
"""
import json
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue

COMMANDS = {'accept': '.uno:AcceptAllTrackedChanges', 'reject': '.uno:RejectAllTrackedChanges'}


def prop(name, value):
    item = PropertyValue()
    item.Name = name
    item.Value = value
    return item


def count_redlines(document):
    enumeration = document.getRedlines().createEnumeration()
    total = 0
    while enumeration.hasMoreElements():
        enumeration.nextElement()
        total += 1
    return total


def connect(pipe, process, deadline):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
    while True:
        try:
            return resolver.resolve('uno:pipe,name=' + pipe + ';urp;StarOffice.ComponentContext')
        except Exception:
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('LibreOffice did not accept a UNO connection')
            time.sleep(0.25)


def run_item(desktop, dispatcher, item):
    document = None
    for attempt in range(3):
        # A loaded desktop can transiently refuse a load under heavy host load; retry it.
        document = desktop.loadComponentFromURL(uno.systemPathToFileUrl(os.path.abspath(item['input'])), '_blank', 0,
                                                (prop('Hidden', True),))
        if document is not None:
            break
        time.sleep(1 + attempt)
    if document is None:
        raise RuntimeError('LibreOffice could not load ' + item['input'])
    try:
        before = count_redlines(document)
        if item['operation'] in COMMANDS:
            dispatcher.executeDispatch(document.getCurrentController().getFrame(), COMMANDS[item['operation']], '', 0, ())
        elif item['operation'] != 'load':
            raise ValueError('Unknown LibreOffice operation: ' + item['operation'])
        after = count_redlines(document)
        document.storeToURL(uno.systemPathToFileUrl(os.path.abspath(item['output'])), (prop('FilterName', 'MS Word 2007 XML'),))
    finally:
        document.close(True)
    return {'redlinesBefore': before, 'redlinesAfter': after}


def main():
    job = json.load(sys.stdin)
    pipe = 'docxbench' + str(os.getpid())
    profile = uno.systemPathToFileUrl(os.path.abspath(job['profile']))
    process = subprocess.Popen([job['soffice'], '-env:UserInstallation=' + profile, '--headless', '--invisible',
                                '--nologo', '--norestore', '--nodefault', '--nolockcheck',
                                '--accept=pipe,name=' + pipe + ';urp;StarOffice.ComponentContext'],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    results = []
    desktop = None
    try:
        context = connect(pipe, process, time.monotonic() + 120)
        manager = context.ServiceManager
        desktop = manager.createInstanceWithContext('com.sun.star.frame.Desktop', context)
        dispatcher = manager.createInstanceWithContext('com.sun.star.frame.DispatchHelper', context)
        for item in job['items']:
            try:
                results.append(dict(run_item(desktop, dispatcher, item), input=item['input'], operation=item['operation']))
            except Exception as error:
                # One document LibreOffice cannot handle does not abort the others; the harness decides
                # whether the failure belongs to the candidate or makes the case unmeasured.
                results.append({'input': item['input'], 'operation': item['operation'], 'error': type(error).__name__ + ': ' + str(error)})
    finally:
        if desktop is not None:
            try:
                desktop.terminate()
            except Exception:
                pass
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)
    json.dump({'results': results}, sys.stdout)


if __name__ == '__main__':
    main()
