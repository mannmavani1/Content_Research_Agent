import operator
from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    The shared memory of the agent.
    """

    messages: Annotated[List[BaseMessage], operator.add]
    
    question: str
    
    documents: List[str]

    generation: str