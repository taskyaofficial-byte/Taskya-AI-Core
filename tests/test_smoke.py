def test_registry():
 from backend.app.tools.registry import TOOLS
 assert {'calculate','search_web','browse','run_python','inspect_file'} <= set(TOOLS)
