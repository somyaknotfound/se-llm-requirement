"""The agents of the requirements-engineering system (brief point 4).

Each agent has one responsibility, a declared set of blackboard permissions, and —
where it retrieves — a knowledge-source allowlist. The coordinator
(src/orchestrator.py) decides execution order, owns the approval gates and is the
only component with privileged access to the blackboard.

    stakeholder_interaction   interviews stakeholders, follows up on weak answers
    extraction                turns statements and documents into requirements
    classification            multi-label classification into 13 categories
    conflict_detection        duplicates and contradictions between requirements
    clarification             sends failing requirements back to their stakeholders
    compliance                maps requirements to controls, finds compliance gaps
    security_privacy          STRIDE threat analysis, missing security requirements
    risk_analysis             clinical, security, compliance and project risk register
    validation                29148 quality audit, hallucination audit, confidence
    sdlc_selection            decision factors -> rules + MCDA -> tailored workflow
    documentation             SRS, user stories, use cases, RTM and registers
    human_approval            routes every decision that needs a person
"""

from .approval import HumanApprovalAgent
from .base import Agent, AgentContext, Blackboard, PermissionDenied
from .classification import ClassificationAgent
from .clarification import ClarificationAgent
from .compliance import ComplianceAgent
from .conflict import ConflictDetectionAgent
from .documentation import DocumentationAgent
from .extraction import RequirementExtractionAgent
from .interaction import StakeholderInteractionAgent
from .risk import RiskAnalysisAgent
from .sdlc import SDLCSelectionAgent
from .security_privacy import SecurityPrivacyAgent
from .validation import ValidationAgent

__all__ = [
    "Agent", "AgentContext", "Blackboard", "PermissionDenied",
    "StakeholderInteractionAgent", "RequirementExtractionAgent", "ClassificationAgent",
    "ConflictDetectionAgent", "ClarificationAgent", "ComplianceAgent",
    "SecurityPrivacyAgent", "RiskAnalysisAgent", "ValidationAgent", "SDLCSelectionAgent",
    "DocumentationAgent", "HumanApprovalAgent",
]
