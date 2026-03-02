/**
 * DAX Debugger — interactive expression analysis with D3 flowchart.
 */

function debugMeasure(btn) {
    var expr = btn.getAttribute('data-expression');
    if (!expr) return;
    document.getElementById('debugger-input').value = expr;
    runDebugger();
    var modal = new bootstrap.Modal(document.getElementById('debuggerModal'));
    modal.show();
}

function runDebugger() {
    var expr = document.getElementById('debugger-input').value.trim();
    if (!expr) return;

    var resultsDiv = document.getElementById('debugger-results');
    resultsDiv.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary" role="status"></div></div>';

    var analysisId = window._editorAnalysisId || 0;
    fetch('/debug-dax', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({expression: expr, analysis_id: analysisId})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.error) {
            resultsDiv.innerHTML = '<div class="alert alert-warning">' + data.error + '</div>';
            return;
        }
        renderDebugResults(resultsDiv, data);
    })
    .catch(function(err) {
        resultsDiv.innerHTML = '<div class="alert alert-danger">Error: ' + err.message + '</div>';
    });
}

function renderDebugResults(container, data) {
    var html = '<div class="row g-3">';

    // Complexity badge
    var levelColors = {low:'#22c55e', medium:'#f59e0b', high:'#f97316', very_high:'#ef4444'};
    var color = levelColors[data.complexity.level] || '#6b7280';
    html += '<div class="col-12"><div class="d-flex align-items-center gap-3 mb-2">';
    html += '<span style="font-size:1.3rem;font-weight:800;color:' + color + ';">Complexity: ' + data.complexity.score + '/100</span>';
    html += '<span class="badge" style="background:' + color + '22;color:' + color + ';font-weight:700;">' + data.complexity.level.toUpperCase() + '</span>';
    html += '<span style="color:var(--text-3);font-size:0.82rem;">Nesting: ' + data.complexity.nesting_depth + ' | Functions: ' + data.complexity.function_count + '</span>';
    html += '</div></div>';

    // Context info
    html += '<div class="col-md-6"><div class="card h-100"><div class="card-body">';
    html += '<h6 style="font-weight:700;color:var(--accent);"><i class="bi bi-funnel me-1"></i>Evaluation Context</h6>';
    html += '<div class="mb-2"><span class="badge ' + (data.context_info.has_row_context ? 'bg-warning' : 'bg-secondary') + ' me-1">Row Context</span>';
    html += '<span class="badge ' + (data.context_info.has_filter_context ? 'bg-primary' : 'bg-secondary') + '">Filter Context</span></div>';
    if (data.context_info.iterators.length > 0) {
        html += '<div style="font-size:0.82rem;color:var(--text-2);">Iterators: ' + data.context_info.iterators.join(', ') + '</div>';
    }
    if (data.context_info.context_transitions.length > 0) {
        html += '<div style="font-size:0.82rem;color:var(--text-2);">Transitions: ' + data.context_info.context_transitions.join(', ') + '</div>';
    }
    html += '</div></div></div>';

    // References
    html += '<div class="col-md-6"><div class="card h-100"><div class="card-body">';
    html += '<h6 style="font-weight:700;color:var(--accent);"><i class="bi bi-link-45deg me-1"></i>References</h6>';
    if (data.referenced_columns.length > 0) {
        html += '<div class="mb-2" style="font-size:0.82rem;">';
        data.referenced_columns.forEach(function(c) {
            html += '<span class="badge bg-primary me-1 mb-1">' + c.table + '[' + c.column + ']</span>';
        });
        html += '</div>';
    }
    if (data.referenced_measures.length > 0) {
        html += '<div style="font-size:0.82rem;">';
        data.referenced_measures.forEach(function(m) {
            html += '<span class="badge bg-success me-1 mb-1">[' + m.name + ']</span>';
        });
        html += '</div>';
    }
    if (data.referenced_columns.length === 0 && data.referenced_measures.length === 0) {
        html += '<span style="color:var(--text-3);font-size:0.82rem;">No direct references found</span>';
    }
    html += '</div></div></div>';

    // Functions breakdown
    html += '<div class="col-md-6"><div class="card h-100"><div class="card-body">';
    html += '<h6 style="font-weight:700;color:var(--accent);"><i class="bi bi-braces me-1"></i>Functions Used</h6>';
    html += '<div class="table-responsive"><table class="table table-sm mb-0" style="color:var(--text-1);font-size:0.8rem;">';
    data.functions_used.slice(0, 10).forEach(function(f) {
        html += '<tr><td style="font-weight:600;">' + f.name + '</td><td>' + f.count + 'x</td><td><span class="badge bg-secondary">' + f.category + '</span></td></tr>';
    });
    html += '</table></div></div></div></div>';

    // Warnings
    if (data.warnings.length > 0) {
        html += '<div class="col-md-6"><div class="card h-100"><div class="card-body">';
        html += '<h6 style="font-weight:700;color:#f59e0b;"><i class="bi bi-exclamation-triangle me-1"></i>Warnings</h6>';
        data.warnings.forEach(function(w) {
            html += '<div class="mb-1" style="font-size:0.82rem;color:var(--text-2);"><i class="bi bi-dot"></i>' + w + '</div>';
        });
        html += '</div></div></div>';
    }

    // Flowchart
    html += '<div class="col-12"><div class="card"><div class="card-body">';
    html += '<h6 style="font-weight:700;color:var(--accent);"><i class="bi bi-diagram-2 me-1"></i>Expression Flow</h6>';
    html += '<div id="debugger-flowchart" style="min-height:200px;"></div>';
    html += '</div></div></div>';

    html += '</div>';
    container.innerHTML = html;

    // Render flowchart with D3
    if (data.flowchart_nodes.length > 0 && typeof d3 !== 'undefined') {
        renderDebugFlowchart('debugger-flowchart', data.flowchart_nodes, data.flowchart_edges);
    }
}

function renderDebugFlowchart(containerId, nodes, edges) {
    var container = document.getElementById(containerId);
    var width = container.offsetWidth || 600;
    var height = Math.max(200, nodes.length * 40);

    var svg = d3.select('#' + containerId).append('svg')
        .attr('width', width).attr('height', height);

    var typeColors = {column: '#3b82f6', measure: '#22c55e', function: '#f59e0b', output: '#ef4444'};

    var sim = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(edges).id(function(d) { return d.id; }).distance(80))
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(40));

    var link = svg.selectAll('line').data(edges).enter().append('line')
        .attr('stroke', 'var(--text-3)').attr('stroke-width', 1.5).attr('marker-end', 'url(#arrow)');

    svg.append('defs').append('marker').attr('id', 'arrow').attr('viewBox', '0 0 10 10')
        .attr('refX', 20).attr('refY', 5).attr('markerWidth', 6).attr('markerHeight', 6)
        .attr('orient', 'auto').append('path').attr('d', 'M 0 0 L 10 5 L 0 10 z').attr('fill', 'var(--text-3)');

    var node = svg.selectAll('g.node').data(nodes).enter().append('g').attr('class', 'node');
    node.append('rect').attr('rx', 6).attr('ry', 6).attr('width', 80).attr('height', 28)
        .attr('x', -40).attr('y', -14)
        .attr('fill', function(d) { return (typeColors[d.type] || '#6b7280') + '33'; })
        .attr('stroke', function(d) { return typeColors[d.type] || '#6b7280'; });
    node.append('text').text(function(d) { return d.label.length > 12 ? d.label.substring(0, 12) + '..' : d.label; })
        .attr('text-anchor', 'middle').attr('dy', 4).attr('font-size', '10px').attr('fill', 'var(--text-1)');

    sim.on('tick', function() {
        link.attr('x1', function(d) { return d.source.x; }).attr('y1', function(d) { return d.source.y; })
            .attr('x2', function(d) { return d.target.x; }).attr('y2', function(d) { return d.target.y; });
        node.attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
    });
}
