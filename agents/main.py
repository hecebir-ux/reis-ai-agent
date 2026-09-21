"""Thin multi-agent wrappers. First version keeps routing simple."""

from core.agent.loop import ReisMaxAgent
from core.coder import Coder
from core.debugger import Debugger
from core.tester import Tester
from tools.web_tool import WebTool
from tools.document_tool import DocumentEngine


class MainAgent(ReisMaxAgent):
    pass


class CoderAgent:
    def __init__(self, coder: Coder):
        self.coder = coder


class ResearcherAgent:
    def __init__(self):
        self.web = WebTool()


class TesterAgent:
    def __init__(self):
        self.tester = Tester()


class DebuggerAgent:
    def __init__(self, debugger: Debugger):
        self.debugger = debugger


class DocumentAgent:
    def __init__(self):
        self.docs = DocumentEngine()
