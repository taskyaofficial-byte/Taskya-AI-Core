from ..config import TAVILY_API_KEY
def search_web(query,max_results=5):
    if not TAVILY_API_KEY:return {"error":"TAVILY_API_KEY is not configured"}
    from tavily import TavilyClient
    return TavilyClient(api_key=TAVILY_API_KEY).search(query=query,search_depth="advanced",max_results=max_results,include_answer=True)
