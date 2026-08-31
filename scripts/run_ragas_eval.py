import sys
import asyncio
import argparse
from loguru import logger

# Add project root to sys.path
sys.path.insert(0, ".")

from app.services.evaluation_service import EvaluationService

async def main():
    parser = argparse.ArgumentParser(description="Run Dynamic RAGAs Benchmark Evaluation")
    parser.add_argument(
        "--mode",
        choices=["all_documents", "single_document"],
        default="all_documents",
        help="Evaluation mode: 'all_documents' or 'single_document'"
    )
    parser.add_argument("--doc-id", type=int, default=None, help="Target document ID for single_document mode")
    parser.add_argument("--count", type=int, default=2, help="Number of test cases per document")
    parser.add_argument("--title", type=str, default=None, help="Optional title for this evaluation run")
    args = parser.parse_args()

    print("\n" + "="*80)
    print(f"[*] STARTING DYNAMIC RAGAS EVALUATION (Mode: {args.mode})")
    print("="*80 + "\n")

    res = await EvaluationService.run_evaluation(
        user_id=None,
        eval_mode=args.mode,
        document_id=args.doc_id,
        title=args.title,
        cases_per_doc=args.count
    )

    print("\n" + "+" + "-"*78 + "+")
    print(f"| DYNAMIC RAGAS SCORECARD SUMMARY (Run #{res['run_id']})")
    print("+" + "-"*78 + "+")
    print(f"| Overall RAG Score:      {res['overall_score'] * 100:.1f}%")
    print(f"| Faithfulness:           {res['faithfulness'] * 100:.1f}%")
    print(f"| Answer Relevancy:       {res['answer_relevancy'] * 100:.1f}%")
    print(f"| Context Precision:      {res['context_precision'] * 100:.1f}%")
    print(f"| Context Recall:         {res['context_recall'] * 100:.1f}%")
    print(f"| Average Query Latency:  {res['avg_latency_ms']:.0f} ms")
    print(f"| Total Dynamic Cases:    {res['total_cases']}")
    print("+" + "-"*78 + "+\n")

if __name__ == "__main__":
    asyncio.run(main())
