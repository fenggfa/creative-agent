"""专业智能体包。"""

from src.agents.critic import critic_node
from src.agents.director import director_node
from src.agents.plot_architect import plot_architect_node
from src.agents.prose_writer import prose_writer_node
from src.agents.researcher import researcher_node
from src.agents.reviewer import reviewer_node
from src.agents.writer import writer_node

__all__ = [
    # 核心智能体（整书模式）
    "director_node",
    "plot_architect_node",
    "prose_writer_node",
    "critic_node",
    # 原有智能体（单篇模式）
    "researcher_node",
    "writer_node",
    "reviewer_node",
]
