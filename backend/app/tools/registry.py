from .calculator import calculate
from .search import search_web
from .workspace import list_files,read_file,write_artifact
TOOLS={
"calculate":{"description":"Safely calculate arithmetic.","parameters":{"type":"object","properties":{"expression":{"type":"string"}},"required":["expression"]},"fn":calculate},
"search_web":{"description":"Search the live web for current information.","parameters":{"type":"object","properties":{"query":{"type":"string"},"max_results":{"type":"integer"}},"required":["query"]},"fn":search_web},
"list_files":{"description":"List safe workspace files.","parameters":{"type":"object","properties":{}},"fn":list_files},
"read_file":{"description":"Read a UTF-8 workspace file.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},"fn":read_file},
"write_artifact":{"description":"Create a text, HTML, CSV or JSON artifact.","parameters":{"type":"object","properties":{"filename":{"type":"string"},"content":{"type":"string"}},"required":["filename","content"]},"fn":write_artifact}}
def schemas():
    return [{"type":"function","function":{"name":n,"description":x["description"],"parameters":x["parameters"]}} for n,x in TOOLS.items()]
