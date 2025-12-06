import gzip
import io
import json
import os
import shutil
import sys
import threading
import traceback

# Try to import yaml, but don't fail if it's missing (fallback to JSON or defaults)
try:
    import yaml
except ImportError:
    yaml = None

# --- LOGGING ---
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any, Dict, List, Optional, Tuple, Type, Union

logging.basicConfig(
    filename="carbon_lsp.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)

# --- DEFAULT SETTINGS (from Settings.yaml) ---
DEFAULT_SETTINGS = {
    "PropertiesName": "__Properties__",
    "AttributesName": "__Attributes__",
    "TagsName": "__Tags__",
    "SourceName": "__Source__",
    "StringifiedPropertyName": "S__",
    "DuplicatedAttributeName": "__DuplicatedIndex__",
    "UnnamedTableName": "__Unnamed__",
    "ServerHost": "localhost",
    "ServerPort": 6969,
    "ServerType": "POST GET",
    "PropertiesFileExtension": "yaml",
    "SourceFileExtension": "luau",
    "CleanUpBeforeImportInVSC": False,
    "CleanUpBeforeImportInRS": False,
    "SynchronizationVSCDebounceTime": 10.0,
    "SynchronizationRSDebounceTime": 0.1,
    "MaximumRSScriptLength": 199999,
    "MaximumLengthRSScriptContainer": "Folder",
    "ExportFromVSCMaximumLength": False,
    "ExportFromRSDuplicated": True,
    "ExportFromRSDataChunkSize": 819200,
    "ExportFromRSPropertyBlacklist": ["Name", "Parent", "Disabled"],
    "StatusHeader": {"Request-Type": "GETStatus"},
    "SettingsHeader": {"Request-Type": "POSTGETSettings"},
    "DataHeader": {"Request-Type": "POSTGETData"},
    "LIVEHeader": {"Request-Frequency": "LIVE"},
}

# --- GLOBAL STATE ---
Settings = DEFAULT_SETTINGS.copy()
ScriptPath = os.getcwd()
BasePath = os.path.join(ScriptPath, "game")
Chunks = {}
Server = None
ServerThread = None

# --- CARBON LOGIC ---


def LoadSettings():
    global Settings
    # Try to load from Settings.yaml in current directory
    settings_path = os.path.join(ScriptPath, "Settings.yaml")
    if os.path.exists(settings_path):
        try:
            if yaml:
                with open(settings_path, "r") as f:
                    user_settings = yaml.safe_load(f)
                    Settings.update(user_settings)
                logging.info("Loaded Settings.yaml")
            else:
                logging.warning(
                    "Settings.yaml found but PyYAML not installed. Using defaults."
                )
        except Exception as e:
            logging.error(f"Error loading Settings.yaml: {e}")
    else:
        logging.info("No Settings.yaml found, using defaults.")


def LogException(e, context):
    logging.error(f"Exception during {context}: {e}")
    logging.error(traceback.format_exc())


def IsDataGZipped(Data):
    return Data[:2] == b"\x1f\x8b"


def DeletePath(Path):
    if os.path.isdir(Path):
        shutil.rmtree(Path)
    else:
        os.remove(Path)


def write_sourcemap(script_map: Dict[str, str], output: str = "sourcemap.json") -> None:
    output_path = os.path.join(ScriptPath, output)
    sourcemap = {"scripts": script_map}
    try:
        with open(output_path, "w") as f:
            json.dump(sourcemap, f, indent=2)
        logging.info(f"Sourcemap written to {os.path.abspath(output_path)}")
    except Exception as e:
        LogException(e, f"write sourcemap to {output_path}!")


def Import(Data, Path=None, IsLIVE=False, Sourcemap=None):
    if Path is None:
        Path = BasePath

    PN = Settings.get("PropertiesName")
    SN = Settings.get("SourceName")
    PropertiesFileName = f"{PN}.{Settings.get('PropertiesFileExtension').lower()}"
    SourceFileName = f"{SN}.{Settings.get('SourceFileExtension').lower()}"
    UseYAML = "y" in Settings.get("PropertiesFileExtension").lower()

    IsRoot = Sourcemap is None
    if IsRoot:
        Sourcemap = {}

    if IsRoot and not IsLIVE and Settings.get("CleanUpBeforeImportInVSC"):
        if os.path.isdir(BasePath):
            for ImportedServiceFolder in os.listdir(BasePath):
                DeletePath(os.path.join(BasePath, ImportedServiceFolder))

    for Key, Value in Data.items():
        NewPath = os.path.join(Path, Key)

        if Key == SN:
            try:
                with open(
                    os.path.join(Path, SourceFileName), "w", encoding="utf-8"
                ) as File:
                    File.write(Value)

                if Sourcemap is not None:
                    RelPath = os.path.relpath(Path, BasePath)
                    RobloxPath = RelPath.replace(os.sep, "/")
                    LocalPath = os.path.join(Path, SourceFileName)
                    LocalRelPath = os.path.relpath(LocalPath, ScriptPath)
                    Sourcemap[RobloxPath] = LocalRelPath.replace(os.sep, "/")
            except Exception as e:
                LogException(e, f"write Source File for {Path}!")

        elif Key == PN:
            try:
                with open(
                    os.path.join(Path, PropertiesFileName), "w", encoding="utf-8"
                ) as File:
                    if UseYAML and yaml:
                        yaml.dump(
                            Value,
                            File,
                            default_flow_style=False,
                            allow_unicode=True,
                            sort_keys=False,
                        )
                    else:
                        json.dump(Value, File, indent=2)
            except Exception as e:
                LogException(e, f"write Properties File for {Path}!")

        else:
            os.makedirs(NewPath, exist_ok=True)
            Import(Value, NewPath, IsLIVE=IsLIVE, Sourcemap=Sourcemap)

    if IsRoot:
        write_sourcemap(Sourcemap)


def GetInstanceDetails(InstanceFullPath, Hierarchy):
    PN = Settings.get("PropertiesName")
    SN = Settings.get("SourceName")
    PropertiesFileName = f"{PN}.{Settings.get('PropertiesFileExtension').lower()}"
    SourceFileName = f"{SN}.{Settings.get('SourceFileExtension').lower()}"
    UseYAML = "y" in Settings.get("PropertiesFileExtension").lower()

    PropertyBlacklist = Settings.get("ExportFromRSPropertyBlacklist")
    PropertiesPath = os.path.join(InstanceFullPath, PropertiesFileName)

    try:
        with open(PropertiesPath, "r", encoding="utf-8") as File:
            if UseYAML and yaml:
                Properties = yaml.safe_load(File)
            else:
                Properties = json.load(File)
    except Exception as e:
        # It's common for folders not to have properties files if they are just containers
        # LogException(e, f'read {PropertiesPath}!')
        return Hierarchy

    Ascendants = os.path.relpath(InstanceFullPath, BasePath).split(os.sep)
    Path = Hierarchy

    for i, AscendantName in enumerate(Ascendants):
        if AscendantName not in Path:
            Path[AscendantName] = {PN: {}}

        Path = Path[AscendantName]

        AscendantPath = os.path.join(BasePath, *Ascendants[: (i + 1)])
        AscendantPropertiesFile = os.path.join(AscendantPath, PropertiesFileName)
        AscendantSourceFile = os.path.join(AscendantPath, SourceFileName)

        if os.path.isfile(AscendantPropertiesFile):
            if os.path.exists(AscendantSourceFile):
                try:
                    with open(AscendantSourceFile, "r", encoding="utf-8") as File:
                        DescendantSource = File.read()
                except Exception as e:
                    LogException(e, f"read {AscendantSourceFile}!")
                    continue

                if len(DescendantSource) < Settings.get("MaximumRSScriptLength"):
                    Path[SN] = DescendantSource
                else:
                    if Settings.get("ExportFromVSCMaximumLength"):
                        Path[SN] = "---> Source was over 199,999..."
                    else:
                        Path[SN] = DescendantSource

            try:
                with open(AscendantPropertiesFile, "r", encoding="utf-8") as File:
                    if UseYAML and yaml:
                        DescendantProperties = yaml.safe_load(File)
                    else:
                        DescendantProperties = json.load(File)
            except Exception as e:
                LogException(e, f"trying to read {AscendantPropertiesFile}!")
                continue

            for Property, Value in DescendantProperties.items():
                if Property not in PropertyBlacklist:
                    Path[PN][Property] = Value

    return Hierarchy


def Export(ScriptToSynchronize=None):
    Hierarchy = {}
    SourceFileName = (
        f"{Settings.get('SourceName')}.{Settings.get('SourceFileExtension').lower()}"
    )

    if ScriptToSynchronize:
        Hierarchy = GetInstanceDetails(os.path.abspath(ScriptToSynchronize), Hierarchy)
    else:
        for File, _, FileChildren in os.walk(BasePath):
            if SourceFileName in FileChildren:
                Hierarchy = GetInstanceDetails(File, Hierarchy)

    return Hierarchy


def GetHandler(POSTEnabled=True, GETEnabled=True):
    class RequestHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                if not POSTEnabled:
                    self.send_error(405, "POST method not allowed")
                    return

                OK = True
                StatusHeader = Settings.get("StatusHeader")
                SettingsHeader = Settings.get("SettingsHeader")
                DataHeader = Settings.get("DataHeader")
                LIVEHeader = Settings.get("LIVEHeader")

                TypeHeaderName = list(DataHeader.keys())[0]
                FrequencyHeaderName = list(LIVEHeader.keys())[0]

                RequestType = self.headers.get(TypeHeaderName, "").lower()
                RequestFrequency = (
                    self.headers.get(FrequencyHeaderName, "").lower()
                    == LIVEHeader[FrequencyHeaderName]
                )

                length = int(self.headers.get("Content-Length", 0))
                Data = self.rfile.read(length)

                if IsDataGZipped(Data):
                    with gzip.GzipFile(fileobj=io.BytesIO(Data), mode="rb") as File:
                        Data = File.read()

                if RequestType != StatusHeader[TypeHeaderName].lower():
                    Data = json.loads(Data.decode("utf-8"))

                if RequestType == SettingsHeader[TypeHeaderName].lower():
                    Settings.update(Data)  # Update global settings

                elif RequestType == DataHeader[TypeHeaderName].lower():
                    Index = Data["Index"]
                    Total = Data["Total"]
                    Chunk = Data["Chunk"]

                    Chunks[Index] = Chunk
                    logging.info(f"Received chunk {Index}/{Total}")

                    if len(Chunks) >= Total:
                        if Settings.get("CleanUpBeforeImportInVSC"):
                            DeletePath(BasePath)

                        Import(
                            json.loads("".join(Chunks[i] for i in sorted(Chunks))),
                            BasePath,
                            RequestFrequency,
                        )
                        Chunks.clear()
                        logging.info("Reconstructed hierarchy")

                elif RequestType == StatusHeader[TypeHeaderName].lower():
                    pass

                else:
                    self.send_error(400, "Bad Request Type")
                    OK = False

                if OK:
                    self.send_response(200)
                    self.end_headers()

            except Exception as e:
                self.send_error(500, "Unexpected error")
                LogException(e, "POST handler")

        def do_GET(self):
            try:
                if not GETEnabled:
                    self.send_error(405, "GET method not allowed")
                    return

                OK = True
                StatusHeader = Settings.get("StatusHeader")
                SettingsHeader = Settings.get("SettingsHeader")
                DataHeader = Settings.get("DataHeader")
                TypeHeaderName = list(DataHeader.keys())[0]

                RequestType = self.headers.get(TypeHeaderName, "").lower()
                Response = None

                if RequestType == SettingsHeader[TypeHeaderName].lower():
                    Response = Settings

                elif RequestType == DataHeader[TypeHeaderName].lower():
                    Response = Export(None)  # Export all

                elif RequestType == StatusHeader[TypeHeaderName].lower():
                    Response = {"Status": "Alive"}

                else:
                    self.send_error(400, "Bad Request Type")
                    OK = False

                if OK:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()

                if Response is None:
                    Response = {"Status": "No data available"}

                self.wfile.write(json.dumps(Response).encode("utf-8"))

            except Exception as e:
                self.send_error(500, "Unexpected error")
                LogException(e, "GET handler")

    return RequestHandler


# --- LSP ADAPTER LOGIC ---


def write_json_rpc(response):
    body = json.dumps(response)
    message = f"Content-Length: {len(body)}\r\n\r\n{body}"
    sys.stdout.write(message)
    sys.stdout.flush()


def run_server():
    LoadSettings()
    host = Settings.get("ServerHost")
    port = Settings.get("ServerPort")

    # Ensure BasePath exists
    os.makedirs(BasePath, exist_ok=True)

    try:
        server = HTTPServer((host, port), GetHandler())
        logging.info(f"Carbon Server running on {host}:{port}")
        server.serve_forever()
    except Exception as e:
        logging.error(f"Server failed to start: {e}")


def main():
    # Start Carbon Server in background thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    logging.info("LSP Adapter started")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            content_length = 0
            if line.startswith("Content-Length:"):
                content_length = int(line.split(":")[1].strip())
                sys.stdin.readline()  # Empty line

            if content_length > 0:
                body = sys.stdin.read(content_length)
                request = json.loads(body)

                method = request.get("method")
                req_id = request.get("id")

                if method == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "capabilities": {"textDocumentSync": 0},
                            "serverInfo": {"name": "carbon-lsp", "version": "0.1"},
                        },
                    }
                    write_json_rpc(response)
                elif method == "shutdown":
                    write_json_rpc({"jsonrpc": "2.0", "id": req_id, "result": None})
                elif method == "exit":
                    break
                elif method == "initialized":
                    pass
                elif method and method.startswith("textDocument/"):
                    pass
        except Exception as e:
            logging.error(f"LSP Error: {e}")
            break


if __name__ == "__main__":
    main()
