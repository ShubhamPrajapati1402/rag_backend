from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.models.document import Base

class EvaluationRun(Base):
    """Tracks a complete RAGAs evaluation execution session."""
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False, default="Full System Evaluation")
    eval_mode = Column(String(50), nullable=False, default="all_documents")  # "baseline", "all_documents", "single_document"
    total_cases = Column(Integer, default=0)
    
    # Aggregated RAGAs Scores (0.0 to 1.0)
    faithfulness_score = Column(Float, default=0.0)
    answer_relevancy_score = Column(Float, default=0.0)
    context_precision_score = Column(Float, default=0.0)
    context_recall_score = Column(Float, default=0.0)
    overall_rag_score = Column(Float, default=0.0)
    
    avg_latency_ms = Column(Float, default=0.0)
    status = Column(String(50), default="COMPLETED")  # "RUNNING", "COMPLETED", "FAILED"
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))
    
    cases = relationship("EvaluationCase", back_populates="run", cascade="all, delete-orphan")


class EvaluationCase(Base):
    """Tracks individual evaluated question, context, metrics, and LLM-as-a-Judge reasoning."""
    __tablename__ = "evaluation_cases"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    document_name = Column(String(255), nullable=True)
    
    question = Column(Text, nullable=False)
    ground_truth = Column(Text, nullable=True)
    generated_answer = Column(Text, nullable=False)
    retrieved_contexts = Column(JSON, default=list)  # List of chunk strings
    
    # Granular Scores for this case
    faithfulness = Column(Float, default=0.0)
    answer_relevancy = Column(Float, default=0.0)
    context_precision = Column(Float, default=0.0)
    context_recall = Column(Float, default=0.0)
    
    # Detailed Judge Audit
    claims_evaluation = Column(JSON, default=list)  # [{claim: str, supported: bool, reason: str}]
    judge_reasoning = Column(Text, nullable=True)
    latency_ms = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))

    run = relationship("EvaluationRun", back_populates="cases")
