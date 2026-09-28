import os

class ComputerController:
    """Optional host computer control. Disabled unless TASKYA_COMPUTER_CONTROL=true."""
    def __init__(self): self.enabled=os.getenv('TASKYA_COMPUTER_CONTROL','false').lower()=='true'
    def guard(self):
        if not self.enabled: raise PermissionError('Computer control is disabled by default')
    def click(self, x:int, y:int):
        self.guard()
        try:
            import pyautogui
        except ImportError as e: raise RuntimeError('Install pyautogui to enable computer control') from e
        pyautogui.click(x,y); return {'ok':True,'x':x,'y':y}
    def screenshot(self, path='artifacts/computer.png'):
        self.guard()
        import pyautogui
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True); pyautogui.screenshot(path); return {'path':path}
