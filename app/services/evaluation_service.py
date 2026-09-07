import time
from typing import List, Dict, Any, Optional
from loguru import logger

from app.db.session import SessionLocal
from app.models.evaluation import EvaluationRun, EvaluationCase
from app.models.document import Document
from app.services.rag.graph import rag_agent_app
from app.evaluation.ragas_engine import RagasEvaluator
from app.evaluation.synthetic_generator import SyntheticTestGenerator


class EvaluationService:
    """
    Executes 100% dynamic RAGAs benchmark evaluations across uploaded documents
    and persists audit logs to PostgreSQL.
    """

    @classmethod
    async def run_evaluation(
        cls,
        user_id: Optional[int] = None,
        eval_mode: str = "all_documents",
        document_id: Optional[int] = None,
        title: Optional[str] = None,
        cases_per_doc: int = 2
    ) -> Dict[str, Any]:
        """
        Executes a full dynamic evaluation run across uploaded documents.
        Generates synthetic test cases from actual PostgreSQL chunks on the fly.
        """
        db = SessionLocal()
        run_title = title or f"RAG Evaluation ({eval_mode.replace('_', ' ').title()})"
        
        # 1. Create Run Record
        eval_run = EvaluationRun(
            user_id=user_id,
            title=run_title,
            eval_mode=eval_mode,
            status="RUNNING"
        )
        db.add(eval_run)
        db.commit()
        db.refresh(eval_run)

        try:
            # 2. Collect dynamic test cases from PostgreSQL
            test_cases: List[Dict[str, Any]] = []
            if eval_mode == "single_document" and document_id:
                test_cases = await SyntheticTestGenerator.generate_tests_for_document(
                    document_id=document_id,
                    count=cases_per_doc
                )
            else:
                test_cases = await SyntheticTestGenerator.generate_tests_for_all_documents(
                    cases_per_doc=cases_per_doc
                )

            if not test_cases:
                raise ValueError("No uploaded documents or extractable content found in database to evaluate. Please upload at least one document first.")

            eval_run.total_cases = len(test_cases)
            db.commit()

            case_results = []
            total_latency = 0.0

            # 3. Execute RAG pipeline and evaluate each test case
            for idx, tc in enumerate(test_cases, start=1):
                question = tc["question"]
                ground_truth = tc.get("ground_truth", "")
                doc_name = tc.get("document_name", "Unknown Document")
                doc_id = tc.get("document_id")

                logger.info(f"[EvaluationService] Running Test {idx}/{len(test_cases)}: '{question[:60]}'...")
                
                t_start = time.time()
                # Run LangGraph pipeline
                state_input = {
                    "question": question,
                    "messages": [{"role": "user", "content": question}],
                    "summary": ""
                }
                result = await rag_agent_app.ainvoke(state_input)
                latency_ms = (time.time() - t_start) * 1000
                total_latency += latency_ms

                answer = result.get("generation", "")
                docs = result.get("documents", [])
                contexts = [d.get("text_content", "") for d in docs]

                # Run RAGAs evaluator on this turn
                eval_metrics = await RagasEvaluator.evaluate_single_turn(
                    question=question,
                    answer=answer,
                    contexts=contexts,
                    ground_truth=ground_truth
                )

                # Persist EvaluationCase
                eval_case = EvaluationCase(
                    run_id=eval_run.id,
                    document_id=doc_id,
                    document_name=doc_name,
                    question=question,
                    ground_truth=ground_truth,
                    generated_answer=answer,
                    retrieved_contexts=contexts[:5],
                    faithfulness=eval_metrics["faithfulness"],
                    answer_relevancy=eval_metrics["answer_relevancy"],
                    context_precision=eval_metrics["context_precision"],
                    context_recall=eval_metrics["context_recall"],
                    claims_evaluation=eval_metrics["claims_evaluation"],
                    latency_ms=round(latency_ms, 1)
                )
                db.add(eval_case)
                db.commit()
                db.refresh(eval_case)

                case_results.append(eval_case)

            # 4. Compute Aggregate Scores
            if case_results:
                avg_faith = sum(c.faithfulness for c in case_results) / len(case_results)
                avg_rel = sum(c.answer_relevancy for c in case_results) / len(case_results)
                avg_prec = sum(c.context_precision for c in case_results) / len(case_results)
                avg_rec = sum(c.context_recall for c in case_results) / len(case_results)
                avg_latency = total_latency / len(case_results)
                overall = (avg_faith * 0.35) + (avg_rel * 0.25) + (avg_prec * 0.20) + (avg_rec * 0.20)
            else:
                avg_faith = avg_rel = avg_prec = avg_rec = avg_latency = overall = 0.0

            eval_run.faithfulness_score = round(avg_faith, 3)
            eval_run.answer_relevancy_score = round(avg_rel, 3)
            eval_run.context_precision_score = round(avg_prec, 3)
            eval_run.context_recall_score = round(avg_rec, 3)
            eval_run.overall_rag_score = round(overall, 3)
            eval_run.avg_latency_ms = round(avg_latency, 1)
            eval_run.status = "COMPLETED"
            db.commit()
            db.refresh(eval_run)

            logger.info(f"╔═══════════════════════════════════════════════════════════════════════")
            logger.info(f"║ [EvaluationService] DYNAMIC EVALUATION RUN #{eval_run.id} COMPLETED")
            logger.info(f"║ 📊 Overall RAG Score:    {overall * 100:.1f}%")
            logger.info(f"║ 🛡️ Faithfulness:         {avg_faith * 100:.1f}%")
            logger.info(f"║ 🎯 Answer Relevancy:     {avg_rel * 100:.1f}%")
            logger.info(f"║ 🔍 Context Precision:    {avg_prec * 100:.1f}%")
            logger.info(f"║ 📚 Context Recall:       {avg_rec * 100:.1f}%")
            logger.info(f"║ ⚡ Average Latency:      {avg_latency:.0f}ms")
            logger.info(f"╚═══════════════════════════════════════════════════════════════════════")

            return {
                "run_id": eval_run.id,
                "title": eval_run.title,
                "status": "COMPLETED",
                "total_cases": eval_run.total_cases,
                "faithfulness": eval_run.faithfulness_score,
                "answer_relevancy": eval_run.answer_relevancy_score,
                "context_precision": eval_run.context_precision_score,
                "context_recall": eval_run.context_recall_score,
                "overall_score": eval_run.overall_rag_score,
                "avg_latency_ms": eval_run.avg_latency_ms,
                "created_at": eval_run.created_at.isoformat() if eval_run.created_at else None
            }

        except Exception as e:
            logger.error(f"[EvaluationService] Evaluation run failed: {e}")
            eval_run.status = "FAILED"
            eval_run.error_message = str(e)
            db.commit()
            raise e
        finally:
            db.close()

    @classmethod
    def get_evaluation_runs(cls, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns recent evaluation runs."""
        db = SessionLocal()
        try:
            runs = db.query(EvaluationRun).order_by(EvaluationRun.id.desc()).limit(limit).all()
            return [
                {
                    "id": r.id,
                    "title": r.title,
                    "eval_mode": r.eval_mode,
                    "total_cases": r.total_cases,
                    "faithfulness_score": r.faithfulness_score,
                    "answer_relevancy_score": r.answer_relevancy_score,
                    "context_precision_score": r.context_precision_score,
                    "context_recall_score": r.context_recall_score,
                    "overall_rag_score": r.overall_rag_score,
                    "avg_latency_ms": r.avg_latency_ms,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in runs
            ]
        finally:
            db.close()

    @classmethod
    def get_run_details(cls, run_id: int) -> Optional[Dict[str, Any]]:
        """Returns details and granular test cases of an evaluation run."""
        db = SessionLocal()
        try:
            run = db.query(EvaluationRun).filter(EvaluationRun.id == run_id).first()
            if not run:
                return None

            cases = db.query(EvaluationCase).filter(EvaluationCase.run_id == run_id).all()
            return {
                "id": run.id,
                "title": run.title,
                "eval_mode": run.eval_mode,
                "total_cases": run.total_cases,
                "faithfulness_score": run.faithfulness_score,
                "answer_relevancy_score": run.answer_relevancy_score,
                "context_precision_score": run.context_precision_score,
                "context_recall_score": run.context_recall_score,
                "overall_rag_score": run.overall_rag_score,
                "avg_latency_ms": run.avg_latency_ms,
                "status": run.status,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "cases": [
                    {
                        "id": c.id,
                        "document_name": c.document_name,
                        "question": c.question,
                        "ground_truth": c.ground_truth,
                        "generated_answer": c.generated_answer,
                        "retrieved_contexts": c.retrieved_contexts,
                        "faithfulness": c.faithfulness,
                        "answer_relevancy": c.answer_relevancy,
                        "context_precision": c.context_precision,
                        "context_recall": c.context_recall,
                        "claims_evaluation": c.claims_evaluation,
                        "latency_ms": c.latency_ms
                    }
                    for c in cases
                ]
            }
        finally:
            db.close()

    @classmethod
    def delete_run(cls, run_id: int) -> bool:
        """Deletes an evaluation run and all its associated test cases."""
        db = SessionLocal()
        try:
            run = db.query(EvaluationRun).filter(EvaluationRun.id == run_id).first()
            if not run:
                return False
            db.query(EvaluationCase).filter(EvaluationCase.run_id == run_id).delete(synchronize_session=False)
            db.delete(run)
            db.commit()
            return True
        finally:
            db.close()
