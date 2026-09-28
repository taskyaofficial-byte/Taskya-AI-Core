import json, urllib.request

class MCPClient:
    """Minimal HTTP JSON tool discovery/call foundation; adapters can be added per MCP server."""
    def __init__(self, base_url): self.base_url=base_url.rstrip('/')
    def list_tools(self): return self._get('/tools')
    def call(self, name, arguments=None): return self._post('/tools/call', {'name':name,'arguments':arguments or {}})
    def _get(self,p):
        with urllib.request.urlopen(self.base_url+p, timeout=15) as r: return json.loads(r.read())
    def _post(self,p,data):
        req=urllib.request.Request(self.base_url+p, data=json.dumps(data).encode(), headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
