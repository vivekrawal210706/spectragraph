/**
 * SpectraGraph — Interactive Graph Builder
 * Cytoscape.js graph editor with node/edge creation, node renaming, sample & random
 * graph generation, JSON/CSV import/export, spectral analysis navigation, and persistence.
 */
document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    const canvasContainer = document.getElementById('graphCanvas');
    if (!canvasContainer || typeof cytoscape === 'undefined') {
        return;
    }

    // ==========================================
    // 1. State
    // ==========================================
    let cy = null;
    let mode = 'default'; // 'default' | 'add-node' | 'add-edge-source' | 'add-edge-target'
    let edgeSourceNode = null;
    let nodeCounter = 1;
    let currentGraphId = null;
    let isDirty = false;

    // ==========================================
    // 2. DOM References
    // ==========================================
    const addNodeBtn = document.getElementById('addNodeBtn');
    const addEdgeBtn = document.getElementById('addEdgeBtn');
    const removeSelectedBtn = document.getElementById('removeSelectedBtn');
    const sampleDropdownBtn = document.getElementById('sampleDropdownBtn');
    const sampleDropdownMenu =
        document.getElementById('sampleDropdownMenu') ||
        document.getElementById('sampleMenu') ||
        document.getElementById('sampleDropdown') ||
        (sampleDropdownBtn ? sampleDropdownBtn.nextElementSibling : null);
    const loadSampleBtn = document.getElementById('loadSampleBtn');
    const randomGraphBtn = document.getElementById('randomGraphBtn');
    const randomGraphDialog = document.getElementById('randomGraphDialog');
    const clearGraphBtn = document.getElementById('clearGraphBtn');
    const relayoutBtn = document.getElementById('relayoutBtn');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomFitBtn = document.getElementById('zoomFitBtn');
    const importBtn = document.getElementById('importBtn');
    const importFileInput = document.getElementById('importFileInput');
    const exportBtn = document.getElementById('exportBtn');
    const exportDropdownMenu =
        document.getElementById('exportDropdownMenu') ||
        document.getElementById('exportMenu') ||
        (exportBtn && exportBtn.nextElementSibling && exportBtn.nextElementSibling.classList && exportBtn.nextElementSibling.classList.contains('dropdown-menu')
            ? exportBtn.nextElementSibling
            : null);
    const exportFormatSelect = document.getElementById('exportFormatSelect');
    const saveGraphBtn = document.getElementById('saveGraphBtn');
    const analyzeBtn = document.getElementById('analyzeBtn');

    const graphNameInput = document.getElementById('graphNameInput');
    const graphDescInput = document.getElementById('graphDescInput');
    const nodeCountStat = document.getElementById('nodeCountStat');
    const edgeCountStat = document.getElementById('edgeCountStat');
    const densityStat = document.getElementById('densityStat');

    const modeIndicator = document.getElementById('modeIndicator');
    const modeText = document.getElementById('modeText');

    const noSelectionMsg = document.getElementById('noSelectionMsg');
    const selectedInfo = document.getElementById('selectedInfo');
    const selectedType = document.getElementById('selectedType');
    const selectedId = document.getElementById('selectedId');
    const selectedLabel = document.getElementById('selectedLabel');
    const selectedDegree = document.getElementById('selectedDegree');
    const degreeRow = document.getElementById('degreeRow');
    const endpointsRow = document.getElementById('endpointsRow');
    const selectedEndpoints = document.getElementById('selectedEndpoints');

    const renameInput = document.getElementById('renameInput');
    const renameBtn =
        document.getElementById('renameBtn') ||
        document.getElementById('renameNodeBtn') ||
        document.getElementById('applyRenameBtn') ||
        (renameInput && renameInput.nextElementSibling && renameInput.nextElementSibling.tagName === 'BUTTON'
            ? renameInput.nextElementSibling
            : null);
    const renameSection =
        document.getElementById('renameSection') ||
        document.getElementById('renameNodeSection') ||
        document.getElementById('renameContainer') ||
        document.getElementById('renameBox') ||
        document.getElementById('renameRow') ||
        document.getElementById('nodeRenameGroup') ||
        (renameInput ? renameInput.parentElement : null);

    function notify(message, type = 'info', duration = 3000) {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type, duration);
        }
    }

    // ==========================================
    // 3. Cytoscape Initialization
    // ==========================================
    cy = cytoscape({
        container: canvasContainer,
        elements: [],
        boxSelectionEnabled: true,
        userZoomingEnabled: false,
        minZoom: 0.25,
        maxZoom: 2.5,
        style: [
            {
                selector: 'node',
                style: {
                    'width': 38,
                    'height': 38,
                    'background-color': '#1f1f3a',
                    'border-width': 2,
                    'border-color': '#5b7ba3',
                    'label': 'data(label)',
                    'color': '#e0e0e8',
                    'font-size': 11,
                    'font-family': 'Inter, sans-serif',
                    'font-weight': 600,
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'overlay-opacity': 0
                }
            },
            {
                selector: 'node:selected',
                style: {
                    'border-color': '#3d8b8b',
                    'border-width': 3
                }
            },
            {
                selector: 'node.edge-source-active',
                style: {
                    'background-color': '#2a2a4d',
                    'border-color': '#3d8b8b',
                    'border-width': 3,
                    'border-style': 'dashed'
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
            },
            {
                selector: 'edge:selected',
                style: {
                    'line-color': '#3d8b8b',
                    'width': 3
                }
            }
        ],
        layout: {
            name: 'cose',
            animate: true,
            animationDuration: 500
        }
    });

    window.graphBuilderCy = cy;

    // ==========================================
    // 4. Mode & UI Helpers
    // ==========================================
    function setMode(newMode, instruction = '', preserveSource = false) {
        mode = newMode;

        if (addNodeBtn) addNodeBtn.classList.remove('active', 'btn-active');
        if (addEdgeBtn) addEdgeBtn.classList.remove('active', 'btn-active');

        if (!preserveSource) {
            cy.nodes().removeClass('edge-source-active');
            edgeSourceNode = null;
        }

        if (mode === 'add-node') {
            cy.autoungrabify(false);
            if (addNodeBtn) addNodeBtn.classList.add('active', 'btn-active');
            canvasContainer.style.cursor = 'crosshair';
            showModeBar(instruction || 'Add Node Mode — Click anywhere on the canvas to place a vertex.');
        } else if (mode === 'add-edge-source') {
            cy.autoungrabify(true);
            if (addEdgeBtn) addEdgeBtn.classList.add('active', 'btn-active');
            canvasContainer.style.cursor = 'pointer';
            showModeBar(instruction || 'Add Edge Mode — Click the source vertex.');
        } else if (mode === 'add-edge-target') {
            cy.autoungrabify(true);
            if (addEdgeBtn) addEdgeBtn.classList.add('active', 'btn-active');
            canvasContainer.style.cursor = 'pointer';
            showModeBar(instruction || 'Add Edge Mode — Click the target vertex to connect.');
        } else {
            cy.autoungrabify(false);
            canvasContainer.style.cursor = 'default';
            hideModeBar();
        }
    }

    function showModeBar(text) {
        if (!modeIndicator || !modeText) return;
        modeText.textContent = text;
        modeIndicator.style.display = 'flex';
    }

    function hideModeBar() {
        if (!modeIndicator) return;
        modeIndicator.style.display = 'none';
    }

    function isElementVisible(el) {
        if (!el) return false;
        if (el.style.display === 'none') return false;
        return el.classList.contains('show') || el.classList.contains('open') || getComputedStyle(el).display !== 'none';
    }

    function setDropdownVisible(menu, visible) {
        if (!menu) return;
        if (visible) {
            menu.style.display = 'block';
            menu.classList.add('show', 'open');
        } else {
            menu.style.display = 'none';
            menu.classList.remove('show', 'open');
        }
    }

    function closeAllDropdowns() {
        setDropdownVisible(sampleDropdownMenu, false);
        setDropdownVisible(exportDropdownMenu, false);
    }

    function runLayout(forceRandomize = false) {
        if (!cy || cy.nodes().length === 0) return;

        // Check if all nodes sit at the same coordinate (e.g., all 0,0)
        const nodes = cy.nodes();
        let allSame = nodes.length > 1;
        if (allSame) {
            const p0 = nodes[0].position();
            for (let i = 1; i < nodes.length; i++) {
                const pi = nodes[i].position();
                if (Math.abs(pi.x - p0.x) > 1 || Math.abs(pi.y - p0.y) > 1) {
                    allSame = false;
                    break;
                }
            }
        }

        cy.layout({
            name: 'cose',
            animate: true,
            animationDuration: 600,
            refresh: 20,
            fit: true,
            padding: 40,
            randomize: forceRandomize || allSame,
            componentSpacing: 75,
            nodeRepulsion: 450000,
            nodeOverlap: 20,
            idealEdgeLength: 75,
            edgeElasticity: 100
        }).run();
    }

    // ==========================================
    // 5. Panel Statistics & Selection Inspector
    // ==========================================
    function updateStats() {
        if (!cy) return;
        const nNodes = cy.nodes().length;
        const nEdges = cy.edges().length;
        const density = nNodes >= 2 ? (2 * nEdges) / (nNodes * (nNodes - 1)) : 0;

        if (nodeCountStat) nodeCountStat.textContent = nNodes;
        if (edgeCountStat) edgeCountStat.textContent = nEdges;
        if (densityStat) densityStat.textContent = density.toFixed(3);
    }

    function showSelectedInfo(element) {
        if (!element) {
            clearSelectedInfo();
            return;
        }

        if (noSelectionMsg) noSelectionMsg.style.display = 'none';
        if (selectedInfo) selectedInfo.style.display = 'block';

        if (element.isNode()) {
            if (selectedType) {
                selectedType.textContent = 'Node';
                selectedType.className = 'badge badge-primary';
            }
            if (selectedId) selectedId.textContent = element.id();
            if (selectedLabel) selectedLabel.textContent = element.data('label') || element.id();

            if (degreeRow) degreeRow.style.display = 'flex';
            if (endpointsRow) endpointsRow.style.display = 'none';
            if (selectedDegree) selectedDegree.textContent = element.connectedEdges().length;

            if (renameSection) renameSection.style.display = '';
            if (renameInput) {
                renameInput.value = element.data('label') || element.id();
                renameInput.disabled = false;
            }
        } else if (element.isEdge()) {
            const srcNode = cy.getElementById(element.data('source'));
            const tgtNode = cy.getElementById(element.data('target'));
            const srcText = srcNode.length ? (srcNode.data('label') || srcNode.id()) : element.data('source');
            const tgtText = tgtNode.length ? (tgtNode.data('label') || tgtNode.id()) : element.data('target');

            if (selectedType) {
                selectedType.textContent = 'Edge';
                selectedType.className = 'badge badge-cyan';
            }
            if (selectedId) selectedId.textContent = element.id();
            if (selectedLabel) selectedLabel.textContent = `${srcText} — ${tgtText}`;

            if (degreeRow) degreeRow.style.display = 'none';
            if (endpointsRow) endpointsRow.style.display = 'flex';
            if (selectedEndpoints) selectedEndpoints.textContent = `${srcText} \u2194 ${tgtText}`;

            if (renameSection) renameSection.style.display = 'none';
        }
    }

    function clearSelectedInfo() {
        if (selectedInfo) selectedInfo.style.display = 'none';
        if (noSelectionMsg) noSelectionMsg.style.display = 'block';
        if (renameSection) renameSection.style.display = 'none';
    }

    // Initialize rename section hidden until a node is selected
    if (renameSection) {
        renameSection.style.display = 'none';
    }

    // ==========================================
    // 6. Canvas Event Listeners
    // ==========================================
    cy.on('tap', function (evt) {
        if (evt.target === cy) {
            if (mode === 'add-node') {
                while (cy.getElementById('n' + nodeCounter).length > 0) {
                    nodeCounter++;
                }
                const newId = 'n' + nodeCounter;
                const newLabel = 'v' + nodeCounter;
                nodeCounter++;

                cy.add({
                    group: 'nodes',
                    data: { id: newId, label: newLabel },
                    position: { x: evt.position.x, y: evt.position.y }
                });

                isDirty = true;
                updateStats();
                notify(`Node ${newLabel} added.`, 'success', 1500);
            } else {
                clearSelectedInfo();
            }
        }
    });

    cy.on('tap', 'node', function (evt) {
        const clickedNode = evt.target;

        if (mode === 'add-edge-source') {
            edgeSourceNode = clickedNode;
            edgeSourceNode.addClass('edge-source-active');
            setMode('add-edge-target', `Source: ${edgeSourceNode.data('label') || edgeSourceNode.id()}. Click target vertex.`, true);
        } else if (mode === 'add-edge-target') {
            if (!edgeSourceNode) {
                setMode('add-edge-source');
                return;
            }
            const targetNode = clickedNode;

            if (targetNode.id() === edgeSourceNode.id()) {
                notify('Self-loops are not allowed in simple graphs.', 'error');
                return;
            }

            const duplicate = cy.edges().filter(e => {
                const s = e.data('source');
                const t = e.data('target');
                return (
                    (s === edgeSourceNode.id() && t === targetNode.id()) ||
                    (s === targetNode.id() && t === edgeSourceNode.id())
                );
            });

            if (duplicate.length > 0) {
                notify('An edge already exists between these vertices.', 'error');
                return;
            }

            const edgeId = `e_${edgeSourceNode.id()}_${targetNode.id()}`;
            cy.add({
                group: 'edges',
                data: {
                    id: edgeId,
                    source: edgeSourceNode.id(),
                    target: targetNode.id()
                }
            });

            isDirty = true;
            notify(
                `Connected ${edgeSourceNode.data('label') || edgeSourceNode.id()} and ${targetNode.data('label') || targetNode.id()}.`,
                'success',
                1800
            );

            setMode('default');
            updateStats();
        } else {
            showSelectedInfo(clickedNode);
        }
    });

    cy.on('tap', 'edge', function (evt) {
        if (mode === 'default') {
            showSelectedInfo(evt.target);
        }
    });

    cy.on('select', 'node, edge', function () {
        if (mode === 'default') {
            const selected = cy.$(':selected');
            if (selected.length > 0) {
                showSelectedInfo(selected[0]);
            }
        }
    });

    cy.on('unselect', function () {
        setTimeout(() => {
            const selected = cy.$(':selected');
            if (selected.length === 0) {
                clearSelectedInfo();
            } else {
                showSelectedInfo(selected[0]);
            }
        }, 30);
    });

    cy.on('add remove', function () {
        updateStats();
    });

    cy.on('dragfree', 'node', function () {
        isDirty = true;
    });

    if (graphNameInput) {
        graphNameInput.addEventListener('input', () => { isDirty = true; });
    }
    if (graphDescInput) {
        graphDescInput.addEventListener('input', () => { isDirty = true; });
    }

    // ==========================================
    // 7. Rename Node
    // ==========================================
    function renameSelectedNode() {
        const selectedNodes = cy.$('node:selected');
        if (selectedNodes.length === 0) {
            notify('Please select a node to rename.', 'info');
            return;
        }
        const node = selectedNodes[0];
        const newLabel = renameInput ? renameInput.value.trim() : '';
        if (!newLabel) {
            notify('Node label cannot be empty.', 'error');
            if (renameInput) renameInput.focus();
            return;
        }

        cy.getElementById(node.id()).data('label', newLabel);
        isDirty = true;
        if (selectedLabel) selectedLabel.textContent = newLabel;
        notify(`Renamed node to "${newLabel}".`, 'success', 1500);
    }

    if (renameBtn) {
        renameBtn.addEventListener('click', renameSelectedNode);
    }
    if (renameInput) {
        renameInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                renameSelectedNode();
            }
        });
    }

    // ==========================================
    // 8. Save & Load Graph Data
    // ==========================================
    function loadGraphData(rawData, preserveCurrentId = false) {
        const graphObj = rawData && rawData.graph
            ? {
                  ...rawData.graph,
                  nodes: rawData.nodes || rawData.graph.nodes,
                  edges: rawData.edges || rawData.graph.edges
              }
            : (rawData || {});

        cy.elements().remove();
        clearSelectedInfo();
        setMode('default');

        const nodeIdMap = {};    // DB / payload node id -> cytoscape id
        const nodeIndexMap = {}; // 0-based index -> cytoscape id
        const nodeLabelMap = {}; // label -> cytoscape id
        let hasValidPositions = false;

        if (Array.isArray(graphObj.nodes)) {
            graphObj.nodes.forEach((n, i) => {
                const cyId = 'n' + (i + 1);
                nodeIndexMap[i] = cyId;
                if (n.id !== undefined && n.id !== null) {
                    nodeIdMap[String(n.id)] = cyId;
                }
                const label = n.label || cyId;
                nodeLabelMap[label] = cyId;

                const px = n.position_x !== undefined && n.position_x !== null ? n.position_x : n.x;
                const py = n.position_y !== undefined && n.position_y !== null ? n.position_y : n.y;
                const hasPos = px !== undefined && px !== null && py !== undefined && py !== null && !(Number(px) === 0 && Number(py) === 0);
                if (hasPos) hasValidPositions = true;

                cy.add({
                    group: 'nodes',
                    data: { id: cyId, label: label },
                    position: hasPos ? { x: Number(px), y: Number(py) } : undefined
                });
            });
            nodeCounter = graphObj.nodes.length + 1;
        } else {
            nodeCounter = 1;
        }

        if (Array.isArray(graphObj.edges)) {
            const seenEdges = new Set();
            graphObj.edges.forEach(e => {
                let srcId = null;
                let tgtId = null;

                if (e.source_node_id !== undefined && e.source_node_id !== null) {
                    srcId = nodeIdMap[String(e.source_node_id)];
                } else if (e.source !== undefined && e.source !== null) {
                    srcId = nodeIdMap[String(e.source)] ||
                        (typeof e.source === 'number' || /^\d+$/.test(String(e.source)) ? nodeIndexMap[Number(e.source)] : null) ||
                        nodeLabelMap[String(e.source)];
                }

                if (e.target_node_id !== undefined && e.target_node_id !== null) {
                    tgtId = nodeIdMap[String(e.target_node_id)];
                } else if (e.target !== undefined && e.target !== null) {
                    tgtId = nodeIdMap[String(e.target)] ||
                        (typeof e.target === 'number' || /^\d+$/.test(String(e.target)) ? nodeIndexMap[Number(e.target)] : null) ||
                        nodeLabelMap[String(e.target)];
                }

                if (srcId && tgtId && srcId !== tgtId) {
                    const pairKey = srcId < tgtId ? `${srcId}__${tgtId}` : `${tgtId}__${srcId}`;
                    if (!seenEdges.has(pairKey)) {
                        seenEdges.add(pairKey);
                        cy.add({
                            group: 'edges',
                            data: {
                                id: `e_${srcId}_${tgtId}`,
                                source: srcId,
                                target: tgtId
                            }
                        });
                    }
                }
            });
        }

        if (graphNameInput) {
            graphNameInput.value = graphObj.name || 'Untitled Graph';
        }
        if (graphDescInput) {
            graphDescInput.value = graphObj.description || '';
        }

        if (!preserveCurrentId) {
            const resolvedId = rawData.graph_id ?? graphObj.id ?? null;
            currentGraphId = resolvedId !== undefined ? resolvedId : null;
        }

        isDirty = false;
        runLayout(!hasValidPositions);
        updateStats();
    }

    async function saveGraph() {
        if (cy.nodes().length === 0) {
            notify('Cannot save an empty graph. Add at least one vertex.', 'error');
            return null;
        }

        const name = (graphNameInput ? graphNameInput.value.trim() : '') || 'Untitled Graph';
        const description = graphDescInput ? graphDescInput.value.trim() : '';

        const nodes = cy.nodes().map(n => ({
            label: n.data('label') || n.id(),
            x: Math.round(n.position('x')),
            y: Math.round(n.position('y'))
        }));

        const nodeIdToIndex = {};
        cy.nodes().forEach((n, i) => {
            nodeIdToIndex[n.id()] = i;
        });

        const edges = cy.edges().map(e => ({
            source: nodeIdToIndex[e.data('source')],
            target: nodeIdToIndex[e.data('target')]
        }));

        const payload = { name, description, nodes, edges };

        const url = currentGraphId ? `/api/graphs/${currentGraphId}` : '/api/graphs';
        const method = currentGraphId ? 'PUT' : 'POST';

        try {
            if (saveGraphBtn) saveGraphBtn.disabled = true;
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const data = await res.json();
                currentGraphId = data.graph_id || data.id || (data.graph && data.graph.id) || currentGraphId;
                isDirty = false;
                notify('Graph saved.', 'success');
                return currentGraphId;
            } else {
                let errMsg = 'Failed to save graph.';
                try {
                    const errData = await res.json();
                    if (errData && errData.error) errMsg = errData.error;
                } catch (_) {}
                notify(errMsg, 'error');
                return null;
            }
        } catch (err) {
            notify('Network error while saving graph.', 'error');
            return null;
        } finally {
            if (saveGraphBtn) saveGraphBtn.disabled = false;
        }
    }

    // ==========================================
    // 9. Sample & Random Graph Loaders
    // ==========================================
    async function loadSample(type) {
        closeAllDropdowns();
        try {
            const res = await fetch('/api/graphs/sample', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: type })
            });

            if (!res.ok) {
                let errMsg = 'Failed to load sample graph.';
                try {
                    const errData = await res.json();
                    if (errData && errData.error) errMsg = errData.error;
                } catch (_) {}
                notify(errMsg, 'error');
                return;
            }

            const data = await res.json();
            // Sample generators return an unsaved template unless backend explicitly returns an ID
            currentGraphId = data.graph_id ?? (data.graph && data.graph.id) ?? data.id ?? null;
            loadGraphData(data, true);
            notify(`Loaded ${type.replace('_', ' ')} sample graph.`, 'success');
        } catch (err) {
            notify('Network error while loading sample graph.', 'error');
        }
    }

    function openRandomDialog() {
        closeAllDropdowns();
        if (!randomGraphDialog) return;
        if (typeof randomGraphDialog.showModal === 'function' && randomGraphDialog.tagName === 'DIALOG') {
            randomGraphDialog.showModal();
        } else {
            randomGraphDialog.style.display = 'flex';
            randomGraphDialog.classList.add('show', 'open');
        }
    }

    function closeRandomDialog() {
        if (!randomGraphDialog) return;
        if (typeof randomGraphDialog.close === 'function' && randomGraphDialog.tagName === 'DIALOG') {
            if (randomGraphDialog.open) randomGraphDialog.close();
        } else {
            randomGraphDialog.style.display = 'none';
            randomGraphDialog.classList.remove('show', 'open');
        }
    }

    async function generateRandomGraph() {
        if (!randomGraphDialog) return;
        const countInput =
            document.getElementById('randomNodeCount') ||
            document.getElementById('nodeCountInput') ||
            document.getElementById('randomNodesInput') ||
            randomGraphDialog.querySelector('input[name="node_count"], input[type="number"]');
        const probInput =
            document.getElementById('randomEdgeProb') ||
            document.getElementById('edgeProbInput') ||
            document.getElementById('edgeProbabilityInput') ||
            document.getElementById('randomProbInput') ||
            randomGraphDialog.querySelector('input[name="edge_probability"], input[step], input[type="range"]');

        const nodeCount = countInput ? parseInt(countInput.value, 10) : 8;
        const edgeProb = probInput ? parseFloat(probInput.value) : 0.4;

        if (isNaN(nodeCount) || nodeCount < 2 || nodeCount > 300) {
            notify('Node count must be between 2 and 300.', 'error');
            return;
        }
        if (isNaN(edgeProb) || edgeProb < 0 || edgeProb > 1) {
            notify('Edge probability must be between 0 and 1.', 'error');
            return;
        }

        try {
            const res = await fetch('/api/graphs/random', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    node_count: nodeCount,
                    edge_probability: edgeProb
                })
            });

            if (!res.ok) {
                let errMsg = 'Failed to generate random graph.';
                try {
                    const errData = await res.json();
                    if (errData && errData.error) errMsg = errData.error;
                } catch (_) {}
                notify(errMsg, 'error');
                return;
            }

            const data = await res.json();
            currentGraphId = data.graph_id ?? (data.graph && data.graph.id) ?? data.id ?? null;
            loadGraphData(data, true);
            closeRandomDialog();
            notify(`Generated random graph (${nodeCount} nodes, p=${edgeProb}).`, 'success');
        } catch (err) {
            notify('Network error generating random graph.', 'error');
        }
    }

    // ==========================================
    // 10. Import & Export
    // ==========================================
    async function exportGraph(format = 'json') {
        closeAllDropdowns();
        if (cy.nodes().length === 0) {
            notify('Graph is empty. Add vertices before exporting.', 'error');
            return;
        }

        let id = currentGraphId;
        if (!id || isDirty) {
            id = await saveGraph();
        }
        if (!id) return;

        const chosenFormat = format || (exportFormatSelect ? exportFormatSelect.value : 'json') || 'json';
        const link = document.createElement('a');
        link.href = `/api/graphs/${id}/export?format=${encodeURIComponent(chosenFormat)}`;
        link.download = '';
        document.body.appendChild(link);
        link.click();
        link.remove();
        notify(`Exporting graph as ${chosenFormat.toUpperCase()}...`, 'info');
    }

    // ==========================================
    // 11. Toolbar & Dialog Event Bindings
    // ==========================================
    if (addNodeBtn) {
        addNodeBtn.addEventListener('click', function () {
            setMode(mode === 'add-node' ? 'default' : 'add-node');
        });
    }

    if (addEdgeBtn) {
        addEdgeBtn.addEventListener('click', function () {
            if (mode === 'add-edge-source' || mode === 'add-edge-target') {
                setMode('default');
                return;
            }
            if (cy.nodes().length < 2) {
                notify('At least two vertices are required to create an edge.', 'info');
                return;
            }
            setMode('add-edge-source');
        });
    }

    if (removeSelectedBtn) {
        removeSelectedBtn.addEventListener('click', function () {
            const selected = cy.$(':selected');
            if (selected.length === 0) {
                notify('Select a vertex or edge to remove.', 'info');
                return;
            }
            const count = selected.length;
            selected.remove();
            isDirty = true;
            clearSelectedInfo();
            updateStats();
            notify(`Removed ${count} selected element${count > 1 ? 's' : ''}.`, 'info');
        });
    }

    if (sampleDropdownBtn && sampleDropdownMenu) {
        sampleDropdownBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            const currentlyVisible = isElementVisible(sampleDropdownMenu);
            closeAllDropdowns();
            setDropdownVisible(sampleDropdownMenu, !currentlyVisible);
        });

        const sampleItems = sampleDropdownMenu.querySelectorAll('[data-sample], [data-type], .sample-item, .dropdown-item');
        sampleItems.forEach(item => {
            if (item.getAttribute('onclick')) return;
            const sampleType = item.getAttribute('data-sample') || item.getAttribute('data-type');
            if (sampleType) {
                item.addEventListener('click', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    loadSample(sampleType);
                });
            }
        });
    } else if (loadSampleBtn) {
        loadSampleBtn.addEventListener('click', () => loadSample('petersen'));
    }

    if (randomGraphBtn && randomGraphDialog) {
        randomGraphBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            openRandomDialog();
        });

        const generateBtn =
            document.getElementById('generateRandomBtn') ||
            document.getElementById('randomGenerateBtn') ||
            document.getElementById('confirmRandomBtn') ||
            randomGraphDialog.querySelector('button[type="submit"], .btn-primary');
        if (generateBtn && !generateBtn.getAttribute('onclick')) {
            generateBtn.addEventListener('click', function (e) {
                e.preventDefault();
                generateRandomGraph();
            });
        }

        const form = randomGraphDialog.querySelector('form');
        if (form) {
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                generateRandomGraph();
            });
        }

        const closeBtns = randomGraphDialog.querySelectorAll(
            '#closeRandomDialogBtn, #cancelRandomBtn, .modal-close, [data-close], [data-dismiss="modal"]'
        );
        closeBtns.forEach(btn => {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                closeRandomDialog();
            });
        });

        randomGraphDialog.addEventListener('click', function (e) {
            if (e.target === randomGraphDialog) {
                closeRandomDialog();
            }
        });
    }

    if (clearGraphBtn) {
        clearGraphBtn.addEventListener('click', function () {
            if (cy.elements().length === 0) return;
            if (!confirm('Clear the entire graph canvas? Unsaved changes will be lost.')) return;

            cy.elements().remove();
            nodeCounter = 1;
            currentGraphId = null;
            isDirty = false;
            clearSelectedInfo();
            updateStats();
            setMode('default');
            notify('Graph cleared.', 'info');
        });
    }

    if (relayoutBtn) {
        relayoutBtn.addEventListener('click', function () {
            runLayout(false);
        });
    }

    function zoomByFactor(factor) {
        if (!cy) return;
        const nextZoom = Math.max(cy.minZoom(), Math.min(cy.maxZoom(), cy.zoom() * factor));
        cy.animate({
            zoom: {
                level: nextZoom,
                renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
            },
            duration: 180
        });
    }

    if (zoomInBtn) {
        zoomInBtn.addEventListener('click', function () { zoomByFactor(1.25); });
    }
    if (zoomOutBtn) {
        zoomOutBtn.addEventListener('click', function () { zoomByFactor(0.8); });
    }
    if (zoomFitBtn) {
        zoomFitBtn.addEventListener('click', function () {
            if (!cy || cy.elements().length === 0) return;
            cy.animate({
                fit: { eles: cy.elements(), padding: 40 },
                duration: 220
            });
        });
    }

    if (importBtn && importFileInput) {
        importBtn.addEventListener('click', function () {
            importFileInput.value = '';
            importFileInput.click();
        });

        importFileInput.addEventListener('change', async function (e) {
            const file = e.target.files && e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/api/graphs/import', {
                    method: 'POST',
                    body: formData
                });
                if (!res.ok) {
                    let errMsg = 'Failed to import graph file.';
                    try {
                        const errData = await res.json();
                        if (errData && errData.error) errMsg = errData.error;
                    } catch (_) {}
                    notify(errMsg, 'error');
                    return;
                }

                const data = await res.json();
                currentGraphId = data.graph_id ?? (data.graph && data.graph.id) ?? data.id ?? null;
                loadGraphData(data, true);
                notify('Graph imported successfully.', 'success');
            } catch (err) {
                notify('Network error while importing graph.', 'error');
            }
        });
    }

    if (exportBtn) {
        if (exportDropdownMenu) {
            exportBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                const currentlyVisible = isElementVisible(exportDropdownMenu);
                closeAllDropdowns();
                setDropdownVisible(exportDropdownMenu, !currentlyVisible);
            });

            const exportItems = exportDropdownMenu.querySelectorAll('[data-format], [data-export-format], .dropdown-item');
            exportItems.forEach(item => {
                if (item.getAttribute('onclick')) return;
                const fmt = item.getAttribute('data-format') || item.getAttribute('data-export-format') || 'json';
                item.addEventListener('click', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    exportGraph(fmt);
                });
            });
        } else {
            exportBtn.addEventListener('click', function () {
                const fmt = exportFormatSelect ? exportFormatSelect.value : 'json';
                exportGraph(fmt);
            });
        }
    }

    const exportJsonBtn = document.getElementById('exportJsonBtn');
    if (exportJsonBtn) {
        exportJsonBtn.addEventListener('click', () => exportGraph('json'));
    }
    const exportCsvBtn = document.getElementById('exportCsvBtn');
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', () => exportGraph('csv'));
    }

    if (saveGraphBtn) {
        saveGraphBtn.addEventListener('click', saveGraph);
    }

    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', async function () {
            if (cy.nodes().length === 0) {
                notify('Add at least one vertex before running spectral analysis.', 'error');
                return;
            }
            let id = currentGraphId;
            if (!id || isDirty) {
                id = await saveGraph();
            }
            if (id) {
                window.location.href = `/analysis?graph_id=${id}`;
            }
        });
    }

    // Close dropdowns on outside click
    document.addEventListener('click', function (e) {
        if (sampleDropdownMenu && isElementVisible(sampleDropdownMenu)) {
            if (!sampleDropdownMenu.contains(e.target) && (!sampleDropdownBtn || !sampleDropdownBtn.contains(e.target))) {
                setDropdownVisible(sampleDropdownMenu, false);
            }
        }
        if (exportDropdownMenu && isElementVisible(exportDropdownMenu)) {
            if (!exportDropdownMenu.contains(e.target) && (!exportBtn || !exportBtn.contains(e.target))) {
                setDropdownVisible(exportDropdownMenu, false);
            }
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function (e) {
        const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
        const isTyping = activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select' ||
            (document.activeElement && document.activeElement.isContentEditable);

        if (e.key === 'Escape') {
            closeAllDropdowns();
            closeRandomDialog();
            setMode('default');
            cy.$(':selected').unselect();
            clearSelectedInfo();
            return;
        }

        if (isTyping) return;

        if (e.key === 'Delete' || e.key === 'Backspace') {
            const selected = cy.$(':selected');
            if (selected.length > 0) {
                e.preventDefault();
                const count = selected.length;
                selected.remove();
                isDirty = true;
                clearSelectedInfo();
                updateStats();
                notify(`Removed ${count} element${count > 1 ? 's' : ''}.`, 'info');
            }
        }
    });

    // Expose helpers globally for inline handlers if used in templates
    window.loadSample = loadSample;
    window.saveGraph = saveGraph;
    window.exportGraph = exportGraph;
    window.loadGraphData = loadGraphData;
    window.generateRandomGraph = generateRandomGraph;

    // ==========================================
    // 12. Auto-load from URL Query Parameters
    // ==========================================
    const urlParams = new URLSearchParams(window.location.search);
    const idParam = urlParams.get('id');
    const sampleParam = urlParams.get('sample');

    if (idParam) {
        fetch(`/api/graphs/${idParam}`)
            .then(res => {
                if (!res.ok) throw new Error('Graph not found');
                return res.json();
            })
            .then(data => {
                currentGraphId = Number(idParam) || idParam;
                loadGraphData(data, true);
                notify(`Loaded "${(data.graph ? data.graph.name : data.name) || 'graph'}"`, 'success');
            })
            .catch(() => {
                notify('Failed to load requested graph.', 'error');
                updateStats();
            });
    } else if (sampleParam) {
        loadSample(sampleParam);
    } else {
        updateStats();
    }
});
