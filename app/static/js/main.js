/**
 * SpectraGraph — Shared Application Utilities
 * Toast notifications, graph deletion API helper, and mobile sidebar toggle.
 */
(function () {
    'use strict';

    /**
     * Display a temporary notification toast.
     * @param {string} message - Message to display
     * @param {'success' | 'error' | 'info' | 'warning'} [type='info'] - Toast variant
     * @param {number} [duration=3000] - Duration in ms before auto-dismiss
     */
    function showToast(message, type = 'info', duration = 3000) {
        let container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container';
            document.body.appendChild(container);
        } else if (!container.classList.contains('toast-container')) {
            container.classList.add('toast-container');
        }

        const toast = document.createElement('div');
        toast.className = `toast toast-${type} show`;

        const msgSpan = document.createElement('span');
        msgSpan.className = 'toast-message';
        msgSpan.textContent = message;
        toast.appendChild(msgSpan);

        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'toast-close';
        closeBtn.setAttribute('aria-label', 'Dismiss notification');
        closeBtn.textContent = '×';
        closeBtn.style.cssText = 'background:none;border:none;color:inherit;font-size:1.2rem;cursor:pointer;margin-left:12px;line-height:1;';

        const dismiss = () => {
            toast.style.opacity = '0';
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.remove();
                }
            }, 300);
        };

        closeBtn.onclick = dismiss;
        toast.appendChild(closeBtn);
        container.appendChild(toast);

        if (duration > 0) {
            setTimeout(dismiss, duration);
        }
    }

    /**
     * Confirm and delete a graph via the REST API.
     * @param {number|string} graphId - Graph ID to delete
     */
    async function deleteGraph(graphId) {
        if (!graphId) return;
        if (!confirm('Delete this graph? This cannot be undone.')) return;

        try {
            const res = await fetch(`/api/graphs/${graphId}`, { method: 'DELETE' });
            if (res.ok) {
                showToast('Graph deleted.', 'success');
                setTimeout(() => location.reload(), 500);
            } else {
                let errMsg = 'Failed to delete graph.';
                try {
                    const data = await res.json();
                    if (data && data.error) errMsg = data.error;
                } catch (_) {
                    // Ignore JSON parse errors
                }
                showToast(errMsg, 'error');
            }
        } catch (e) {
            showToast('Network error.', 'error');
        }
    }

    // Mobile sidebar toggle
    document.addEventListener('DOMContentLoaded', function () {
        const toggle = document.getElementById('sidebarToggle');
        const sidebar = document.getElementById('sidebar');
        if (toggle && sidebar) {
            toggle.onclick = (e) => {
                e.stopPropagation();
                sidebar.classList.toggle('open');
            };
            document.addEventListener('click', (e) => {
                if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && !toggle.contains(e.target)) {
                    sidebar.classList.remove('open');
                }
            });
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && sidebar.classList.contains('open')) {
                    sidebar.classList.remove('open');
                }
            });
        }
    });

    window.showToast = showToast;
    window.deleteGraph = deleteGraph;
})();
