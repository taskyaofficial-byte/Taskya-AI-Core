from .workers.browser import BrowserWorker
from .workers.docker_sandbox import DockerSandbox
from .documents.pipeline import DocumentPipeline
from .computer.control import ComputerController

class AgentRuntime:
    def __init__(self):
        self.browser=BrowserWorker()
        self.sandbox=DockerSandbox()
        self.documents=DocumentPipeline()
        self.computer=ComputerController()
