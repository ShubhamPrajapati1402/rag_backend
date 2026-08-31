tsx_path = r"D:\Learning AI\RAG\rag_frontend\src\components\Evaluation\DeveloperEvaluationDashboard.tsx"

with open(tsx_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. State for confirm dialog
state_old = "const [isTeamModalOpen, setIsTeamModalOpen] = useState(false);"
state_new = """const [isTeamModalOpen, setIsTeamModalOpen] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    desc: string;
    confirmLabel?: string;
    onConfirm: () => void;
  } | null>(null);"""

content = content.replace(state_old, state_new)

# 2. handleRevokeAccess
old_revoke = """  const handleRevokeAccess = async (email: string) => {
    if (!window.confirm(`Revoke developer access for ${email}?`)) return;
    try {
      const res = await fetch(`${BACKEND_BASE_URL}/api/v1/auth/manage-developer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, is_developer: false }),
      });
      const data = await res.json();
      if (res.ok) {
        setTeamMessage({ type: 'success', text: data.message });
        await loadDevelopers();
      } else {
        setTeamMessage({ type: 'error', text: data.detail || 'Failed to revoke' });
      }
    } catch (err: any) {
      setTeamMessage({ type: 'error', text: err.message });
    }
  };"""

new_revoke = """  const handleRevokeAccess = (email: string) => {
    setConfirmDialog({
      isOpen: true,
      title: "Revoke Developer Access?",
      desc: `Are you sure you want to revoke developer privileges from ${email}? They will no longer be able to run RAG benchmarks.`,
      confirmLabel: "Revoke Access",
      onConfirm: async () => {
        try {
          const res = await fetch(`${BACKEND_BASE_URL}/api/v1/auth/manage-developer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email, is_developer: false }),
          });
          const data = await res.json();
          if (res.ok) {
            setTeamMessage({ type: 'success', text: data.message });
            await loadDevelopers();
          } else {
            setTeamMessage({ type: 'error', text: data.detail || 'Failed to revoke' });
          }
        } catch (err: any) {
          setTeamMessage({ type: 'error', text: err.message });
        } finally {
          setConfirmDialog(null);
        }
      }
    });
  };"""

content = content.replace(old_revoke, new_revoke)

# 3. handleDeleteRun
old_delete = """  const handleDeleteRun = async (runId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete Evaluation Run #" + runId + "?")) return;
    try {
      await evaluationService.deleteRun(runId);
      setRuns(prev => prev.filter(r => r.id !== runId));
      if (selectedRun?.id === runId) {
        setSelectedRun(null);
      }
      fetchRuns(true);
    } catch (err: any) {
      console.error('Failed to delete run:', err);
      alert(err.message || 'Failed to delete evaluation run');
    }
  };"""

new_delete = """  const handleDeleteRun = (runId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDialog({
      isOpen: true,
      title: `Delete Evaluation Run #${runId}?`,
      desc: `Are you sure you want to delete Evaluation Run #${runId}? All synthesized QA benchmark metrics and atomic claim audits will be permanently removed.`,
      confirmLabel: "Delete Run",
      onConfirm: async () => {
        try {
          await evaluationService.deleteRun(runId);
          setRuns(prev => prev.filter(r => r.id !== runId));
          if (selectedRun?.id === runId) {
            setSelectedRun(null);
          }
          fetchRuns(true);
        } catch (err: any) {
          console.error('Failed to delete run:', err);
        } finally {
          setConfirmDialog(null);
        }
      }
    });
  };"""

content = content.replace(old_delete, new_delete)

# 4. Add modal JSX right before the final `</div>\n  );\n}`
modal_jsx = """      {/* Custom Confirmation Modal (Identical to Logout Modal) */}
      {confirmDialog && confirmDialog.isOpen && (
        <div className="delete-modal-backdrop anim-fade-in" onClick={() => setConfirmDialog(null)}>
          <div className="delete-modal-card anim-slide-up" onClick={(e) => e.stopPropagation()}>
            <div className="delete-modal-header">
              <h3>{confirmDialog.title}</h3>
              <button className="modal-x" onClick={() => setConfirmDialog(null)}>
                <X size={16} />
              </button>
            </div>
            <p className="delete-modal-desc">
              {confirmDialog.desc}
            </p>
            <div className="delete-modal-actions">
              <button className="btn-cancel" onClick={() => setConfirmDialog(null)}>
                Cancel
              </button>
              <button 
                className="btn-danger-confirm" 
                onClick={confirmDialog.onConfirm}
              >
                {confirmDialog.confirmLabel || "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}"""

# Replace the last `</div>\n  );\n}`
import re
content = re.sub(r'    </div>\s*\n\s*\);\s*\n\}\s*$', modal_jsx, content)

with open(tsx_path, "w", encoding="utf-8") as f:
    f.write(content)

print("TSX updated successfully with Logout-style Modal!")
