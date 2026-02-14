from typing import Dict, Any
from core.graph_manager import GraphManager
from core.attention import AttentionModel
from core.perception import PerceptionModule
from core.initiative import InitiativeEngine
from core.feedback import FeedbackManager

class MnemosyneState:
    gm: GraphManager = None
    am: AttentionModel = None
    pm: PerceptionModule = None
    ie: InitiativeEngine = None
    fm: FeedbackManager = None
    llm: Any = None
    config: Dict = {}

state = MnemosyneState()
