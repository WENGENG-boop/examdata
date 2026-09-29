"""智能层：知识点标注、难度估计、相似题发现、解析生成。

共同约束：
- 只写 source 明确标注为 auto / estimated / rule-based 的行，与官方数据物理隔离；
- 全部确定性，不依赖外部模型服务，可随解析重跑稳定复现；
- 每个结果都带可核对的证据（命中词、特征原值、相似度分量、引用的评分条目）。
"""

from .difficulty import MODEL_VERSION as DIFFICULTY_MODEL_VERSION
from .difficulty import estimate_all
from .explanation import PROMPT_VERSION as EXPLANATION_PROMPT_VERSION
from .explanation import PROVIDER as EXPLANATION_PROVIDER
from .explanation import generate_all as generate_explanations
from .explanation import generate_for_question, review_explanation
from .similarity import METHOD as SIMILARITY_METHOD
from .similarity import find_similar
from .taxonomy import assign_taxonomy, classify_question, sync_taxonomy

__all__ = [
    "DIFFICULTY_MODEL_VERSION",
    "EXPLANATION_PROMPT_VERSION",
    "EXPLANATION_PROVIDER",
    "SIMILARITY_METHOD",
    "assign_taxonomy",
    "classify_question",
    "estimate_all",
    "find_similar",
    "generate_explanations",
    "generate_for_question",
    "review_explanation",
    "sync_taxonomy",
]
