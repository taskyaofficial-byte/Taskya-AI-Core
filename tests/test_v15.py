import sys
sys.path.insert(0,'backend')
from app.workers.browser import BrowserWorker
from app.workers.docker_sandbox import DockerSandbox
from app.documents.pipeline import DocumentPipeline
from app.computer.control import ComputerController

def test_modules_import():
    assert BrowserWorker and DockerSandbox and DocumentPipeline and ComputerController

def test_computer_disabled_by_default(monkeypatch):
    monkeypatch.delenv('TASKYA_COMPUTER_CONTROL', raising=False)
    assert ComputerController().enabled is False
