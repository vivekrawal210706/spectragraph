/**
 * SpectraGraph — Spectral Analysis Display
 * Handles graph selection, spectral analysis execution via POST /api/analyze/<id>,
 * matrix tables, eigenvalue spectrum & plot, connectivity comparison,
 * Fiedler vector bisection visualization, and automated observations.
 */
(function () {
    'use strict';

    let currentGraphId = null;
    let beforePartitionCy = null;
    let afterPartitionCy = null;

    function notify(message, type = 'info', duration = 3000) {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type, duration);
        }
    }

    function firstElement(...ids) {
        for (const id of ids) {
            const el = document.getElementById(id);
            if (el) return el;
        }
        return null;
    }

    // ==========================================
    // 1. Initialization & Graph List Loading
    // ==========================================
    document.addEventListener('DOMContentLoaded', async function () {
        const urlParams = new URLSearchParams(window.location.search);
        const graphIdParam = urlParams.get('graph_id');

        const graphSelect = firstElement('graphSelect', 'graphSelector', 'analysisGraphSelect');
        const runBtn = firstElement('runAnalysisBtn', 'analyzeBtn', 'startAnalysisBtn');
        const changeGraphBtn = firstElement('changeGraphBtn', 'selectAnotherGraphBtn', 'newAnalysisBtn');

        await populateGraphDropdown(graphSelect, graphIdParam);

        if (runBtn && graphSelect) {
            runBtn.addEventListener('click', function () {
                const selectedId = graphSelect.value;
                if (!selectedId) {
                    notify('Please select a graph to analyze.', 'error');
                    return;
                }
                runAnalysis(selectedId);
            });
        } else if (graphSelect) {
            graphSelect.addEventListener('change', function () {
                if (graphSelect.value) {
                    runAnalysis(graphSelect.value);
                }
            });
        }

        if (changeGraphBtn) {
            changeGraphBtn.addEventListener('click', function () {
                const selectionSection = document.getElementById('graphSelectionSection');
                const resultsSection = document.getElementById('analysisResults');
                if (resultsSection) resultsSection.style.display = 'none';
                if (selectionSection) selectionSection.style.display = 'block';
            });
        }

        if (graphIdParam) {
            if (graphSelect) {
                graphSelect.value = graphIdParam;
            }
            runAnalysis(graphIdParam);
        }

        const runDemoBtn = document.getElementById('runDemoBtn');
        if (runDemoBtn) {
            runDemoBtn.addEventListener('click', runDemoSuite);
        }
    });

    async function runDemoSuite() {
        const btn = document.getElementById('runDemoBtn');
        const container = document.getElementById('demoResultsContainer');
        const tbody = document.getElementById('demoResultsBody');
        const summary = document.getElementById('demoFiedlerSummary');
        if (!tbody) return;

        try {
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Running...';
            }
            const res = await fetch('/api/demonstrations');
            if (!res.ok) throw new Error('Failed to run demonstrations');
            const data = await res.json();

            tbody.innerHTML = '';
            (data.demonstrations || []).forEach(row => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${row.name}</strong></td>
                    <td>${row.node_count}</td>
                    <td>${row.edge_count}</td>
                    <td><span class="math-inline">${row.zero_eigenvalue_count}</span></td>
                    <td>${row.bfs_components}</td>
                    <td>${row.union_find_components}</td>
                    <td class="font-mono">${row.lambda_2 !== null ? Number(row.lambda_2).toFixed(4) : '—'}</td>
                    <td><span class="badge ${row.all_agree ? 'badge-success' : 'badge-danger'}">${row.all_agree ? '✓ Agree' : '✗ Mismatch'}</span></td>
                `;
                tbody.appendChild(tr);
            });

            if (summary && data.two_community_split) {
                const s = data.two_community_split;
                summary.innerHTML = `<strong>Two-Community Fiedler Split</strong> (λ₂ = ${Number(s.lambda_2).toFixed(4)}): Group 1 = [${s.group_1_labels.join(', ')}] &nbsp;|&nbsp; Group 2 = [${s.group_2_labels.join(', ')}]`;
            }
            if (container) container.style.display = 'block';
        } catch (err) {
            notify('Could not run 6-graph verification: ' + err.message, 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Run 6-Graph Verification';
            }
        }
    }

    async function populateGraphDropdown(selectEl, preselectId) {
        if (!selectEl) return;
        try {
            const res = await fetch('/api/graphs');
            if (!res.ok) throw new Error('Failed to load graphs');
            const payload = await res.json();
            const graphs = Array.isArray(payload) ? payload : (payload.graphs || []);

            selectEl.innerHTML = '';
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = graphs.length > 0 ? 'Select a saved graph...' : 'No saved graphs found';
            selectEl.appendChild(placeholder);

            graphs.forEach(g => {
                const option = document.createElement('option');
                option.value = String(g.id);
                const vCount = g.node_count !== undefined ? g.node_count : '?';
                const eCount = g.edge_count !== undefined ? g.edge_count : '?';
                option.textContent = `${g.name} (${vCount}V, ${eCount}E)`;
                selectEl.appendChild(option);
            });

            if (preselectId) {
                selectEl.value = String(preselectId);
            }
        } catch (err) {
            notify('Could not load saved graphs list.', 'error');
        }
    }

    // ==========================================
    // 2. Run Spectral Analysis
    // ==========================================
    async function runAnalysis(graphId) {
        currentGraphId = graphId;
        const selectionSection = document.getElementById('graphSelectionSection');
        const loadingSection = document.getElementById('analysisLoading');
        const resultsSection = document.getElementById('analysisResults');

        if (selectionSection) selectionSection.style.display = 'none';
        if (loadingSection) loadingSection.style.display = 'flex';
        if (resultsSection) resultsSection.style.display = 'none';

        try {
            const res = await fetch(`/api/analyze/${graphId}`, { method: 'POST' });
            if (!res.ok) {
                let errMsg = 'Analysis failed';
                try {
                    const errData = await res.json();
                    if (errData && errData.error) errMsg = errData.error;
                } catch (_) {}
                throw new Error(errMsg);
            }

            const data = await res.json();

            if (loadingSection) loadingSection.style.display = 'none';
            if (resultsSection) resultsSection.style.display = 'block';

            displayResults(data);
        } catch (e) {
            if (loadingSection) loadingSection.style.display = 'none';
            if (selectionSection) selectionSection.style.display = 'block';
            notify('Analysis failed: ' + e.message, 'error');
        }
    }

    // ==========================================
    // 3. Display Analysis Results
    // ==========================================
    function displayResults(data) {
        const graphId = data.graph_id || currentGraphId;
        const graphMeta = data.graph || {};
        const graphName = data.graph_name || data.name || graphMeta.name || 'Graph Analysis';

        const adjMatrix = data.adjacency_matrix || [];
        const degMatrix = data.degree_matrix || [];
        const lapMatrix = data.laplacian_matrix || [];

        const rawNodes = data.nodes || graphMeta.nodes || [];
        const rawEdges = data.edges || graphMeta.edges || [];

        const nodeCount =
            data.node_count ?? data.num_nodes ?? (rawNodes.length || adjMatrix.length || 0);
        const edgeCount =
            data.edge_count ?? data.num_edges ??
            (rawEdges.length || countEdgesFromMatrix(adjMatrix));
        const density =
            data.density !== undefined && data.density !== null
                ? Number(data.density)
                : (nodeCount >= 2 ? (2 * edgeCount) / (nodeCount * (nodeCount - 1)) : 0);

        const methodUsed =
            data.method_used || data.eigen_method || data.method || 'Laplacian Eigendecomposition';

        const labels = extractLabels(data, rawNodes, nodeCount);
        const eigenvalues = Array.isArray(data.eigenvalues) ? data.eigenvalues.map(Number) : [];
        const zeroEps = 1e-6;
        const zeroCount =
            data.zero_eigenvalue_count !== undefined
                ? Number(data.zero_eigenvalue_count)
                : eigenvalues.filter(v => Math.abs(v) < zeroEps).length;

        // a. Overview
        setText(firstElement('overviewName', 'overviewGraphName', 'analysisGraphName', 'graphTitleDisplay'), graphName);
        setText(firstElement('overviewNodes', 'overviewNodeCount', 'analysisNodeCount', 'statNodes'), String(nodeCount));
        setText(firstElement('overviewEdges', 'overviewEdgeCount', 'analysisEdgeCount', 'statEdges'), String(edgeCount));
        setText(firstElement('overviewDensity', 'analysisDensity', 'statDensity'), density.toFixed(4));
        setText(firstElement('overviewMethod', 'analysisMethod', 'eigenMethodOverview'), methodUsed);

        // b, c, d. Matrices & Laplacian Verification
        renderMatrix('adjacencyMatrixTable', adjMatrix, labels);
        renderMatrix('degreeMatrixTable', degMatrix, labels);
        renderMatrix('laplacianMatrixTable', lapMatrix, labels);
        renderLaplacianVerification(data, lapMatrix, degMatrix, adjMatrix, eigenvalues);

        // e. Eigenvalues
        renderEigenvalues(eigenvalues, graphId, zeroCount, methodUsed, zeroEps);

        // e2. Null Space
        renderNullSpace(data.null_space, labels);

        // f. Components Comparison
        const spectralCount = data.component_count_spectral ?? zeroCount;
        const bfsCount = data.component_count_bfs;
        const ufCount = data.component_count_union_find;
        renderComponentsComparison(spectralCount, bfsCount, ufCount);

        // g. Fiedler Vector & Spectral Bisection
        const fiedlerInfo = extractFiedlerData(data, labels, rawNodes, eigenvalues, spectralCount);
        renderFiedlerSection(fiedlerInfo, rawNodes, rawEdges, adjMatrix, labels);

        // h. Observations
        renderObservations({
            nodeCount,
            edgeCount,
            density,
            spectralCount,
            bfsCount,
            ufCount,
            fiedlerInfo
        });
    }

    function countEdgesFromMatrix(adj) {
        if (!Array.isArray(adj) || adj.length === 0) return 0;
        let sum = 0;
        for (let i = 0; i < adj.length; i++) {
            for (let j = i + 1; j < adj[i].length; j++) {
                if (adj[i][j]) sum++;
            }
        }
        return sum;
    }

    function extractLabels(data, rawNodes, nodeCount) {
        if (Array.isArray(data.node_labels) && data.node_labels.length > 0) {
            return data.node_labels.map(String);
        }
        if (Array.isArray(data.labels) && data.labels.length > 0) {
            return data.labels.map(String);
        }
        if (Array.isArray(rawNodes) && rawNodes.length > 0) {
            return rawNodes.map((n, i) => String(n.label || n.id || `v${i + 1}`));
        }
        const fallback = [];
        for (let i = 0; i < nodeCount; i++) {
            fallback.push(`v${i + 1}`);
        }
        return fallback;
    }

    function setText(el, value) {
        if (el) el.textContent = value;
    }

    // ==========================================
    // 4. Matrix Renderer & Verification
    // ==========================================
    function renderMatrix(containerId, matrix, labels) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const isTableEl = container.tagName === 'TABLE';
        container.innerHTML = '';

        if (!Array.isArray(matrix) || matrix.length === 0) {
            if (isTableEl) {
                container.innerHTML = '<tbody><tr><td class="text-muted">No matrix data available.</td></tr></tbody>';
            } else {
                const emptyMsg = document.createElement('p');
                emptyMsg.className = 'text-muted';
                emptyMsg.textContent = 'No matrix data available.';
                container.appendChild(emptyMsg);
            }
            return;
        }

        const n = matrix.length;
        const maxDisplay = 15;
        const isTruncated = n > maxDisplay;
        const displayDim = isTruncated ? maxDisplay : n;

        const table = isTableEl ? container : document.createElement('table');
        table.className = 'matrix-table';

        if (isTruncated) {
            const existingNote = container.parentElement && container.parentElement.querySelector('.matrix-truncated-note');
            if (existingNote) existingNote.remove();
            const note = document.createElement('div');
            note.className = 'matrix-truncated-note';
            note.textContent = `Matrix too large to display fully (${n}×${n}) — showing top-left ${maxDisplay}×${maxDisplay} submatrix.`;
            note.style.cssText = 'margin: 8px 10px; font-size: 0.85rem; color: var(--text-secondary, #94a3b8);';
            if (isTableEl && container.parentElement) {
                container.parentElement.insertBefore(note, container);
            } else {
                container.appendChild(note);
            }
        }

        const thead = document.createElement('thead');
        const headRow = document.createElement('tr');
        const cornerTh = document.createElement('th');
        headRow.appendChild(cornerTh);

        for (let j = 0; j < displayDim; j++) {
            const th = document.createElement('th');
            th.textContent = labels[j] !== undefined ? labels[j] : `v${j + 1}`;
            headRow.appendChild(th);
        }
        thead.appendChild(headRow);
        table.appendChild(thead);

        const tbody = document.createElement('tbody');
        for (let i = 0; i < displayDim; i++) {
            const tr = document.createElement('tr');
            const rowTh = document.createElement('th');
            rowTh.textContent = labels[i] !== undefined ? labels[i] : `v${i + 1}`;
            tr.appendChild(rowTh);

            const row = matrix[i] || [];
            for (let j = 0; j < displayDim; j++) {
                const td = document.createElement('td');
                const rawVal = Number(row[j] ?? 0);
                const isZero = Math.abs(rawVal) < 1e-9;
                const isInt = Math.abs(rawVal - Math.round(rawVal)) < 1e-9;

                td.textContent = isZero ? '0' : (isInt ? String(Math.round(rawVal)) : rawVal.toFixed(2));

                if (i === j) td.classList.add('diagonal');
                if (isZero) {
                    td.classList.add('zero');
                } else {
                    td.classList.add('nonzero');
                }

                tr.appendChild(td);
            }
            tbody.appendChild(tr);
        }
        table.appendChild(tbody);

        if (!isTableEl) {
            const scrollWrapper = document.createElement('div');
            scrollWrapper.className = 'matrix-scroll-wrapper';
            scrollWrapper.style.cssText = 'overflow-x: auto; max-width: 100%;';
            scrollWrapper.appendChild(table);
            container.appendChild(scrollWrapper);
        }
    }

    function renderLaplacianVerification(data, L, D, A, eigenvalues) {
        const existingContainer = firstElement('laplacianVerification', 'matrixVerification', 'verificationResults');
        const lapContainer = document.getElementById('laplacianMatrixTable');
        const target = existingContainer || lapContainer;
        if (!target) return;

        const ver = data.laplacian_verification || data.verification || {};
        const checks = [];

        if (Array.isArray(ver)) {
            ver.forEach(item => {
                if (typeof item === 'string') {
                    checks.push({ label: item, passed: true });
                } else if (item && item.label) {
                    checks.push({ label: item.label, passed: Boolean(item.passed ?? true) });
                }
            });
        } else {
            // Compute client-side verification when explicit flags are absent
            let isSymmetric = ver.is_symmetric;
            let rowSumsZero = ver.row_sums_zero;
            let matchesFormula = ver.matches_d_minus_a;

            if (Array.isArray(L) && L.length > 0) {
                if (isSymmetric === undefined) {
                    isSymmetric = true;
                    for (let i = 0; i < L.length && isSymmetric; i++) {
                        for (let j = i + 1; j < L.length; j++) {
                            if (Math.abs((L[i][j] ?? 0) - (L[j][i] ?? 0)) > 1e-6) {
                                isSymmetric = false;
                                break;
                            }
                        }
                    }
                }
                if (rowSumsZero === undefined) {
                    rowSumsZero = L.every(row => Math.abs(row.reduce((acc, v) => acc + Number(v || 0), 0)) < 1e-6);
                }
                if (matchesFormula === undefined && Array.isArray(D) && Array.isArray(A) && D.length === L.length && A.length === L.length) {
                    matchesFormula = true;
                    for (let i = 0; i < L.length && matchesFormula; i++) {
                        for (let j = 0; j < L.length; j++) {
                            if (Math.abs((L[i][j] ?? 0) - ((D[i][j] ?? 0) - (A[i][j] ?? 0))) > 1e-6) {
                                matchesFormula = false;
                                break;
                            }
                        }
                    }
                }
            }

            let isPsd = ver.is_positive_semidefinite ?? ver.positive_semidefinite;
            if (isPsd === undefined && eigenvalues.length > 0) {
                isPsd = eigenvalues.every(ev => ev >= -1e-6);
            }

            if (isSymmetric !== undefined) checks.push({ label: 'Symmetric (L = Lᵀ)', passed: Boolean(isSymmetric) });
            if (rowSumsZero !== undefined) checks.push({ label: 'Zero Row Sums (L·1 = 0)', passed: Boolean(rowSumsZero) });
            if (isPsd !== undefined) checks.push({ label: 'Positive Semi-Definite (λ ≥ 0)', passed: Boolean(isPsd) });
            if (matchesFormula !== undefined) checks.push({ label: 'L = D - A Verified', passed: Boolean(matchesFormula) });
        }

        if (checks.length === 0) return;

        const badgeRow = document.createElement('div');
        badgeRow.className = 'verification-checks';
        badgeRow.style.cssText = 'display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;';

        checks.forEach(c => {
            const badge = document.createElement('span');
            badge.className = `badge ${c.passed ? 'badge-green badge-success' : 'badge-red badge-danger'}`;
            badge.textContent = `${c.passed ? '✓' : '✗'} ${c.label}`;
            badgeRow.appendChild(badge);
        });

        if (existingContainer) {
            existingContainer.innerHTML = '';
            existingContainer.appendChild(badgeRow);
        } else {
            lapContainer.appendChild(badgeRow);
        }
    }

    // ==========================================
    // 5. Eigenvalues & Plot
    // ==========================================
    function renderEigenvalues(eigenvalues, graphId, zeroCount, methodUsed, zeroEps) {
        const listEl = document.getElementById('eigenvalueList');
        if (listEl) {
            listEl.innerHTML = '';
            eigenvalues.forEach((val, idx) => {
                const chip = document.createElement('span');
                chip.className = 'eigenvalue-chip';
                if (Math.abs(val) < zeroEps) {
                    chip.classList.add('zero');
                }
                const displayVal = (Math.abs(val) < 1e-9 ? 0 : val).toFixed(4);
                chip.textContent = displayVal;
                chip.title = `λ${idx + 1} = ${val}`;
                listEl.appendChild(chip);
            });
        }

        const plotImg = firstElement('eigenvaluePlot', 'eigenvaluePlotImg', 'eigenvaluePlotImage', 'spectrumPlotImg');
        if (plotImg && graphId) {
            plotImg.src = `/api/graphs/${graphId}/eigenvalue-plot?t=${Date.now()}`;
            plotImg.style.display = 'block';
        }

        const zeroEl = firstElement('zeroCount', 'zeroEigenvalueCount', 'zeroCountInfo', 'eigenZeroCount');
        if (zeroEl) {
            zeroEl.textContent = zeroEl.id === 'zeroCount'
                ? String(zeroCount)
                : `${zeroCount} eigenvalue(s) ≈ 0 \u2192 ${zeroCount} connected component(s)`;
        }

        const methodEl = firstElement('eigenMethodBadge', 'eigenMethodInfo', 'methodUsed', 'eigenvalueMethod');
        if (methodEl) {
            methodEl.textContent = methodUsed;
        }
    }

    function renderNullSpace(nullSpace, labels) {
        const dimBadge = document.getElementById('nullSpaceDimBadge');
        const expEl = document.getElementById('nullSpaceExplanation');
        const resEl = document.getElementById('nullSpaceResidual');
        const vecContainer = document.getElementById('nullSpaceVectors');
        if (!nullSpace || !vecContainer) return;

        if (dimBadge) dimBadge.textContent = `dim = ${nullSpace.dimension ?? 0}`;
        if (expEl) expEl.textContent = nullSpace.explanation || '';
        if (resEl) resEl.textContent = Number(nullSpace.max_residual ?? 0).toExponential(2);

        vecContainer.innerHTML = '';
        const indicators = nullSpace.component_indicators || [];
        const basis = nullSpace.basis_vectors || [];

        indicators.forEach((vec, idx) => {
            const box = document.createElement('div');
            box.className = 'null-vector-box';
            const formatted = vec.map((v, i) => `${labels[i] || 'v' + (i + 1)}:${v}`).join(' ');
            box.innerHTML = `<div style="color: var(--teal); font-weight: 600; margin-bottom: 4px;">Component Indicator 1<sub>C${idx + 1}</sub></div><div>[${formatted}]</div>`;
            vecContainer.appendChild(box);
        });

        basis.slice(0, 6).forEach((vec, idx) => {
            const box = document.createElement('div');
            box.className = 'null-vector-box';
            const formatted = vec.slice(0, 12).map(v => Number(v).toFixed(3)).join(', ') + (vec.length > 12 ? ', ...' : '');
            box.innerHTML = `<div style="color: var(--accent); font-weight: 600; margin-bottom: 4px;">Null-Space Eigenvector u<sub>${idx + 1}</sub> (Lv ≈ 0)</div><div>[${formatted}]</div>`;
            vecContainer.appendChild(box);
        });
    }

    // ==========================================
    // 6. Components Comparison
    // ==========================================
    function renderComponentsComparison(spectralCount, bfsCount, ufCount) {
        const tableContainer = firstElement('componentsComparisonTable', 'componentsTable', 'componentComparisonContainer');
        const tbodyEl = firstElement('componentsComparisonBody', 'componentComparisonBody');
        const agreementEl = firstElement('agreementStatus', 'componentsAgreement', 'agreementIndicator', 'methodsAgreement');

        const rows = [
            { method: 'Spectral (zero eigenvalues)', value: spectralCount, detail: 'Multiplicity of λ = 0 in L' },
            { method: 'BFS', value: bfsCount, detail: 'Breadth-First Search graph traversal' },
            { method: 'Union-Find', value: ufCount, detail: 'Disjoint-Set Union with path compression' }
        ];

        if (tbodyEl) {
            tbodyEl.innerHTML = '';
            rows.forEach(r => {
                const tr = document.createElement('tr');
                const tdMethod = document.createElement('td');
                tdMethod.innerHTML = `<strong>${r.method}</strong>`;
                const tdCount = document.createElement('td');
                tdCount.textContent = r.value !== undefined && r.value !== null ? String(r.value) : '—';
                const tdDetail = document.createElement('td');
                tdDetail.textContent = r.detail;
                tr.appendChild(tdMethod);
                tr.appendChild(tdCount);
                tr.appendChild(tdDetail);
                tbodyEl.appendChild(tr);
            });
        } else if (tableContainer) {
            tableContainer.innerHTML = '';
            const table = document.createElement('table');
            table.className = 'data-table';
            const thead = document.createElement('thead');
            thead.innerHTML = '<tr><th>Method</th><th>Components</th></tr>';
            table.appendChild(thead);

            const tbody = document.createElement('tbody');
            rows.forEach(r => {
                const tr = document.createElement('tr');
                const tdMethod = document.createElement('td');
                tdMethod.textContent = r.method;
                const tdCount = document.createElement('td');
                tdCount.textContent = r.value !== undefined && r.value !== null ? String(r.value) : '—';
                tr.appendChild(tdMethod);
                tr.appendChild(tdCount);
                tbody.appendChild(tr);
            });
            table.appendChild(tbody);
            tableContainer.appendChild(table);
        }

        const validCounts = [spectralCount, bfsCount, ufCount].filter(v => v !== undefined && v !== null);
        const allMatch =
            validCounts.length === 3 &&
            Number(spectralCount) === Number(bfsCount) &&
            Number(bfsCount) === Number(ufCount);

        const agreementHtml = allMatch
            ? `<span class="agreement-match" style="color: var(--accent-green, #10b981); font-weight: 600;">✓ All three methods agree: ${spectralCount} component(s)</span>`
            : `<span class="agreement-mismatch" style="color: var(--accent-red, #ef4444); font-weight: 600;">⚠ Methods disagree (Spectral: ${spectralCount ?? '?'}, BFS: ${bfsCount ?? '?'}, Union-Find: ${ufCount ?? '?'})</span>`;

        if (agreementEl) {
            agreementEl.innerHTML = agreementHtml;
        } else if (tableContainer) {
            const div = document.createElement('div');
            div.className = 'agreement-indicator';
            div.style.marginTop = '12px';
            div.innerHTML = agreementHtml;
            tableContainer.appendChild(div);
        }
    }

    // ==========================================
    // 7. Fiedler Vector & Partition Visualization
    // ==========================================
    function extractFiedlerData(data, labels, rawNodes, eigenvalues, spectralCount) {
        const fiedler = data.fiedler || {};
        const lambda2 =
            fiedler.lambda_2 ??
            data.lambda_2 ??
            (eigenvalues.length >= 2 ? eigenvalues[1] : null);

        const n = labels.length;
        const rawVec =
            fiedler.fiedler_vector ||
            fiedler.vector ||
            (Array.isArray(fiedler.values) && typeof fiedler.values[0] !== 'object' ? fiedler.values : null) ||
            data.fiedler_vector ||
            [];

        const canPartition =
            fiedler.can_partition !== undefined
                ? Boolean(fiedler.can_partition)
                : (Number(spectralCount) === 1 && n >= 2 && rawVec.length === n);

        const explanation =
            fiedler.explanation ||
            (Number(spectralCount) > 1
                ? 'Fiedler partitioning requires a connected graph (λ₂ > 0).'
                : 'Fiedler partitioning is not available for graphs with fewer than 2 vertices.');

        const rows = [];
        if (canPartition) {
            if (Array.isArray(fiedler.values) && fiedler.values.length > 0 && typeof fiedler.values[0] === 'object') {
                fiedler.values.forEach((entry, i) => {
                    const nodeId = String(entry.node_id ?? entry.id ?? rawNodes[i]?.id ?? i);
                    const label = String(entry.label ?? labels[i] ?? `v${i + 1}`);
                    const val = Number(entry.value ?? 0);
                    const grp = entry.group === 2 || entry.group === 'Group 2' ? 2 : (entry.group === 1 || entry.group === 'Group 1' ? 1 : (val >= 0 ? 1 : 2));
                    rows.push({ index: i, nodeId, label, value: val, group: grp });
                });
            } else {
                const toKey = x => String(typeof x === 'object' && x !== null ? (x.id ?? x.node_id ?? x.label) : x);
                const g1Set = new Set((fiedler.group_1 || []).map(toKey));
                const g2Set = new Set((fiedler.group_2 || []).map(toKey));

                for (let i = 0; i < n; i++) {
                    const nodeId = String(rawNodes[i]?.id ?? i);
                    const label = labels[i] ?? `v${i + 1}`;
                    const val = Number(rawVec[i] ?? 0);

                    let grp;
                    if (Array.isArray(fiedler.groups) && fiedler.groups.length === n) {
                        const rawG = fiedler.groups[i];
                        const isZeroBased = fiedler.groups.includes(0);
                        if (rawG === 2 || rawG === -1 || rawG === 'Group 2' || rawG === 'B' || (isZeroBased && rawG === 1)) {
                            grp = 2;
                        } else {
                            grp = 1;
                        }
                    } else if (g1Set.size > 0 || g2Set.size > 0) {
                        if (g1Set.has(String(i)) || g1Set.has(nodeId) || g1Set.has(label)) {
                            grp = 1;
                        } else if (g2Set.has(String(i)) || g2Set.has(nodeId) || g2Set.has(label)) {
                            grp = 2;
                        } else {
                            grp = val >= 0 ? 1 : 2;
                        }
                    } else {
                        grp = val >= 0 ? 1 : 2;
                    }

                    rows.push({ index: i, nodeId, label, value: val, group: grp });
                }
            }
        }

        const group1Labels = rows.filter(r => r.group === 1).map(r => r.label);
        const group2Labels = rows.filter(r => r.group === 2).map(r => r.label);

        return {
            lambda2,
            canPartition,
            explanation,
            rows,
            group1Labels,
            group2Labels
        };
    }

    function renderFiedlerSection(fiedlerInfo, rawNodes, rawEdges, adjMatrix, labels) {
        const lambda2El = firstElement('lambda2Value', 'fiedlerLambda2', 'lambda2Stat');
        if (lambda2El) {
            lambda2El.textContent =
                fiedlerInfo.lambda2 !== null && fiedlerInfo.lambda2 !== undefined
                    ? Number(fiedlerInfo.lambda2).toFixed(4)
                    : '—';
        }

        const vizSection = firstElement('fiedlerPartitionContent', 'fiedlerPartitionSection', 'partitionVisualization', 'fiedlerVisualization');
        const explanationEl = firstElement('fiedlerExplanation', 'fiedlerUnavailableMsg', 'fiedlerMessage');
        const fiedlerBodyEl = document.getElementById('fiedlerTableBody');
        const fiedlerTableEl = firstElement('fiedlerTable', 'fiedlerVectorTable', 'fiedlerValuesTable');
        const group1El = firstElement('group1Members', 'fiedlerGroup1', 'partitionGroup1');
        const group2El = firstElement('group2Members', 'fiedlerGroup2', 'partitionGroup2');

        if (!fiedlerInfo.canPartition) {
            if (vizSection) vizSection.style.display = 'none';
            if (fiedlerBodyEl) fiedlerBodyEl.innerHTML = '';
            else if (fiedlerTableEl && fiedlerTableEl.tagName !== 'TABLE') fiedlerTableEl.innerHTML = '';
            if (explanationEl) {
                explanationEl.textContent = fiedlerInfo.explanation;
                explanationEl.style.display = 'block';
            }
            if (beforePartitionCy) { beforePartitionCy.destroy(); beforePartitionCy = null; }
            if (afterPartitionCy) { afterPartitionCy.destroy(); afterPartitionCy = null; }
            return;
        }

        if (explanationEl) explanationEl.style.display = 'none';
        if (vizSection) vizSection.style.display = 'block';

        // Fiedler values table
        if (fiedlerBodyEl) {
            fiedlerBodyEl.innerHTML = '';
            fiedlerInfo.rows.forEach(r => {
                const tr = document.createElement('tr');
                const tdLabel = document.createElement('td');
                tdLabel.textContent = r.label;

                const tdVal = document.createElement('td');
                tdVal.className = 'font-mono';
                tdVal.textContent = (Math.abs(r.value) < 1e-9 ? 0 : r.value).toFixed(4);

                const tdGroup = document.createElement('td');
                const badge = document.createElement('span');
                badge.className = `badge ${r.group === 1 ? 'badge-primary' : 'badge-success'}`;
                badge.textContent = `Group ${r.group}`;
                tdGroup.appendChild(badge);

                tr.appendChild(tdLabel);
                tr.appendChild(tdVal);
                tr.appendChild(tdGroup);
                fiedlerBodyEl.appendChild(tr);
            });
        } else if (fiedlerTableEl) {
            fiedlerTableEl.innerHTML = '';
            const table = document.createElement('table');
            table.className = 'data-table';
            table.innerHTML = '<thead><tr><th>Node Label</th><th>Fiedler Value</th><th>Group</th></tr></thead>';
            const tbody = document.createElement('tbody');

            fiedlerInfo.rows.forEach(r => {
                const tr = document.createElement('tr');
                const tdLabel = document.createElement('td');
                tdLabel.textContent = r.label;

                const tdVal = document.createElement('td');
                tdVal.className = 'font-mono';
                tdVal.textContent = (Math.abs(r.value) < 1e-9 ? 0 : r.value).toFixed(4);

                const tdGroup = document.createElement('td');
                const badge = document.createElement('span');
                badge.className = `badge ${r.group === 1 ? 'badge-violet' : 'badge-cyan'}`;
                badge.textContent = `Group ${r.group}`;
                tdGroup.appendChild(badge);

                tr.appendChild(tdLabel);
                tr.appendChild(tdVal);
                tr.appendChild(tdGroup);
                tbody.appendChild(tr);
            });

            table.appendChild(tbody);
            fiedlerTableEl.appendChild(table);
        }

        // Group membership lists
        if (group1El) {
            group1El.textContent = fiedlerInfo.group1Labels.length > 0
                ? fiedlerInfo.group1Labels.join(', ')
                : 'None';
        }
        if (group2El) {
            group2El.textContent = fiedlerInfo.group2Labels.length > 0
                ? fiedlerInfo.group2Labels.join(', ')
                : 'None';
        }

        // Prepare nodes and edges for Cytoscape instances
        const cyNodes = buildCyNodes(rawNodes, labels);
        const cyEdges = buildCyEdges(rawEdges, rawNodes, adjMatrix, labels);

        const beforeColorMap = {};
        const afterColorMap = {};
        fiedlerInfo.rows.forEach(r => {
            beforeColorMap[r.nodeId] = '#5b7ba3';
            afterColorMap[r.nodeId] = r.group === 1 ? '#7c3aed' : '#3d8b8b';
        });

        if (beforePartitionCy) {
            beforePartitionCy.destroy();
            beforePartitionCy = null;
        }
        if (afterPartitionCy) {
            afterPartitionCy.destroy();
            afterPartitionCy = null;
        }

        beforePartitionCy = createCytoscapeInstance('graphBeforePartition', cyNodes, cyEdges, beforeColorMap);

        // Copy exact positions from beforePartitionCy so both graphs align identically
        let alignedNodes = cyNodes;
        if (beforePartitionCy) {
            const posMap = {};
            beforePartitionCy.nodes().forEach(n => {
                posMap[n.id()] = n.position();
            });
            alignedNodes = cyNodes.map(n => ({
                ...n,
                x: posMap[n.id] ? posMap[n.id].x : n.x,
                y: posMap[n.id] ? posMap[n.id].y : n.y
            }));
        }

        afterPartitionCy = createCytoscapeInstance('graphAfterPartition', alignedNodes, cyEdges, afterColorMap, true);
    }

    function buildCyNodes(rawNodes, labels) {
        if (Array.isArray(rawNodes) && rawNodes.length > 0) {
            return rawNodes.map((n, i) => ({
                id: String(n.id ?? i),
                label: String(n.label ?? labels[i] ?? `v${i + 1}`),
                x: n.position_x ?? n.x,
                y: n.position_y ?? n.y
            }));
        }
        return labels.map((lbl, i) => ({
            id: String(i),
            label: lbl
        }));
    }

    function buildCyEdges(rawEdges, rawNodes, adjMatrix, labels) {
        if (Array.isArray(rawEdges) && rawEdges.length > 0) {
            const idLookup = {};
            const idxLookup = {};
            const lblLookup = {};
            (rawNodes || []).forEach((n, i) => {
                const cyId = String(n.id ?? i);
                idLookup[String(n.id ?? i)] = cyId;
                idxLookup[i] = cyId;
                lblLookup[String(n.label ?? labels[i])] = cyId;
            });

            const edges = [];
            rawEdges.forEach((e, i) => {
                const rawSrc = e.source_node_id ?? e.source;
                const rawTgt = e.target_node_id ?? e.target;
                const src = idLookup[String(rawSrc)] ?? idxLookup[Number(rawSrc)] ?? lblLookup[String(rawSrc)];
                const tgt = idLookup[String(rawTgt)] ?? idxLookup[Number(rawTgt)] ?? lblLookup[String(rawTgt)];
                if (src !== undefined && tgt !== undefined && src !== tgt) {
                    edges.push({ id: `e${i}_${src}_${tgt}`, source: src, target: tgt });
                }
            });
            return edges;
        }

        // Reconstruct from adjacency matrix if edge array was omitted
        const edges = [];
        if (Array.isArray(adjMatrix)) {
            for (let i = 0; i < adjMatrix.length; i++) {
                for (let j = i + 1; j < adjMatrix[i].length; j++) {
                    if (adjMatrix[i][j]) {
                        const src = String(rawNodes[i]?.id ?? i);
                        const tgt = String(rawNodes[j]?.id ?? j);
                        edges.push({ id: `e_${src}_${tgt}`, source: src, target: tgt });
                    }
                }
            }
        }
        return edges;
    }

    /**
     * Create a read-only Cytoscape instance for visualization.
     * @param {string} containerId - Target container element ID
     * @param {Array<Object>} nodes - Normalized node objects
     * @param {Array<Object>} edges - Normalized edge objects
     * @param {Object<string, string>} colorMap - Maps node id -> color hex/string
     * @param {boolean} [usePreset=false] - Force preset layout if positions are supplied
     * @returns {Object|null} Cytoscape instance
     */
    function createCytoscapeInstance(containerId, nodes, edges, colorMap, usePreset = false) {
        const container = document.getElementById(containerId);
        if (!container || typeof cytoscape === 'undefined') return null;

        let hasAllPositions = nodes.length > 0 && nodes.every(
            n => n.x !== undefined && n.x !== null && n.y !== undefined && n.y !== null
        );
        if (hasAllPositions && nodes.length > 1) {
            const allZero = nodes.every(n => Number(n.x) === 0 && Number(n.y) === 0);
            if (allZero) hasAllPositions = false;
        }

        const elements = [];
        nodes.forEach(n => {
            const id = String(n.id);
            const nodeColor = (colorMap && (colorMap[id] || colorMap[n.label])) || '#5b7ba3';
            elements.push({
                group: 'nodes',
                data: {
                    id: id,
                    label: n.label || id,
                    color: nodeColor
                },
                position: hasAllPositions ? { x: Number(n.x), y: Number(n.y) } : undefined
            });
        });

        edges.forEach((e, idx) => {
            elements.push({
                group: 'edges',
                data: {
                    id: e.id || `edge_${idx}`,
                    source: String(e.source),
                    target: String(e.target)
                }
            });
        });

        const layoutConfig = (usePreset && hasAllPositions) || hasAllPositions
            ? { name: 'preset', fit: true, padding: 24 }
            : { name: 'cose', animate: false, fit: true, padding: 24, randomize: true };

        const cyInstance = cytoscape({
            container: container,
            elements: elements,
            autoungrabify: true,
            autounselectify: true,
            boxSelectionEnabled: false,
            userPanningEnabled: true,
            userZoomingEnabled: false,
            style: [
                {
                    selector: 'node',
                    style: {
                        'width': 34,
                        'height': 34,
                        'background-color': 'data(color)',
                        'border-width': 2,
                        'border-color': 'rgba(224, 224, 232, 0.35)',
                        'label': 'data(label)',
                        'color': '#e0e0e8',
                        'font-size': 10,
                        'font-weight': 600,
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'overlay-opacity': 0
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': 'rgba(91,123,163,0.5)',
                        'curve-style': 'bezier',
                        'target-arrow-shape': 'none',
                        'overlay-opacity': 0
                    }
                }
            ],
            layout: layoutConfig
        });

        cyInstance.resize();
        cyInstance.fit(undefined, 24);
        return cyInstance;
    }

    // ==========================================
    // 8. Observations
    // ==========================================
    function renderObservations(summary) {
        const listEl = firstElement('observationsList', 'analysisObservations', 'observationsContainer');
        if (!listEl) return;

        const bullets = [];
        bullets.push(`The graph has ${summary.nodeCount} vertices and ${summary.edgeCount} edges.`);
        bullets.push(`Graph density: ${summary.density.toFixed(4)}.`);

        if (Number(summary.spectralCount) === 1) {
            const l2 = summary.fiedlerInfo.lambda2 !== null && summary.fiedlerInfo.lambda2 !== undefined
                ? Number(summary.fiedlerInfo.lambda2).toFixed(4)
                : '—';
            bullets.push(`The graph is connected (λ₂ = ${l2} > 0).`);
        } else {
            bullets.push(
                `The graph is disconnected with ${summary.spectralCount} components (${summary.spectralCount} zero eigenvalues).`
            );
        }

        const counts = [summary.spectralCount, summary.bfsCount, summary.ufCount].filter(v => v !== undefined && v !== null);
        if (counts.length === 3) {
            const agree = Number(counts[0]) === Number(counts[1]) && Number(counts[1]) === Number(counts[2]);
            bullets.push(
                agree
                    ? `All three component-counting methods agree (${counts[0]} component${Number(counts[0]) === 1 ? '' : 's'}).`
                    : `The three component-counting methods disagree (Spectral: ${counts[0]}, BFS: ${counts[1]}, Union-Find: ${counts[2]}).`
            );
        }

        if (summary.fiedlerInfo.canPartition) {
            bullets.push(
                `The Fiedler vector partitions the graph into groups of size ${summary.fiedlerInfo.group1Labels.length} and ${summary.fiedlerInfo.group2Labels.length}.`
            );
        }

        listEl.innerHTML = '';
        bullets.forEach(text => {
            const li = document.createElement('li');
            li.textContent = text;
            listEl.appendChild(li);
        });
    }

    // Expose public helpers
    window.runAnalysis = runAnalysis;
    window.displayResults = displayResults;
    window.renderMatrix = renderMatrix;
    window.createCytoscapeInstance = createCytoscapeInstance;
})();
