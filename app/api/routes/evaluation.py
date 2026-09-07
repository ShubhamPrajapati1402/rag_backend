from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_superuser
from app.models.user import User
from app.services.evaluation_service import EvaluationService
from app.evaluation.synthetic_generator import SyntheticTestGenerator

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

class RunEvaluationRequest(BaseModel):
    title: Optional[str] = None
    eval_mode: str = "all_documents"  # "all_documents" | "single_document"
    document_id: Optional[int] = None
    cases_per_doc: int = 2

@router.post("/run")
async def trigger_evaluation_run(
    req: RunEvaluationRequest,
    current_user: User = Depends(get_current_superuser)
):
    """
    Triggers a dynamic RAGAs evaluation run directly against uploaded PostgreSQL documents.
    Protected: Developer/Superuser only.
    """
    try:
        res = await EvaluationService.run_evaluation(
            user_id=current_user.id if current_user else None,
            eval_mode=req.eval_mode,
            document_id=req.document_id,
            title=req.title,
            cases_per_doc=req.cases_per_doc
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")

@router.get("/runs")
def list_evaluation_runs(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_superuser)
):
    """Fetches historical evaluation runs and summary scorecards. Protected: Developer/Superuser only."""
    return EvaluationService.get_evaluation_runs(limit=limit)

@router.get("/runs/{run_id}")
def get_evaluation_run_details(
    run_id: int,
    current_user: User = Depends(get_current_superuser)
):
    """Fetches detailed metrics and claim-level audits for a specific evaluation run. Protected: Developer/Superuser only."""
    res = EvaluationService.get_run_details(run_id)
    if not res:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return res

@router.delete("/runs/{run_id}")
def delete_evaluation_run(
    run_id: int,
    current_user: User = Depends(get_current_superuser)
):
    """Deletes an evaluation run by ID. Protected: Developer/Superuser only."""
    success = EvaluationService.delete_run(run_id)
    if not success:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return {"message": f"Evaluation run #{run_id} successfully deleted."}

@router.post("/generate-tests/{document_id}")
async def generate_synthetic_tests(
    document_id: int,
    count: int = Query(3, ge=1, le=10),
    current_user: User = Depends(get_current_superuser)
):
    """Generates synthetic QA evaluation test cases from a specified document. Protected: Developer/Superuser only."""
    tests = await SyntheticTestGenerator.generate_tests_for_document(document_id, count=count)
    return {"document_id": document_id, "generated_cases": tests}
