// Power Query Lineage - D3.js force-directed graph
(function() {
    'use strict';

    window.renderPQLineage = function(containerId, data) {
        if (!data || !data.nodes || data.nodes.length === 0) return;

        var container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';

        var width = container.clientWidth || 900;
        var height = 500;

        var nodeColors = { source: '#22c55e', staging: '#f59e0b', final: '#3b82f6' };
        var linkColors = { reference: '#64748b', merge: '#a855f7', append: '#ec4899' };

        var style = getComputedStyle(document.documentElement);
        var textColor = style.getPropertyValue('--text-1').trim() || '#f0f2f5';
        var text2Color = style.getPropertyValue('--text-2').trim() || '#a0aec0';

        var svg = d3.select('#' + containerId)
            .append('svg')
            .attr('width', width)
            .attr('height', height)
            .attr('viewBox', [0, 0, width, height]);

        var g = svg.append('g');
        var zoom = d3.zoom()
            .scaleExtent([0.2, 5])
            .on('zoom', function(event) { g.attr('transform', event.transform); });
        svg.call(zoom);

        // Arrow markers per link type
        var defs = svg.append('defs');
        Object.keys(linkColors).forEach(function(type) {
            defs.append('marker')
                .attr('id', 'pq-arrow-' + type)
                .attr('viewBox', '0 -5 10 10')
                .attr('refX', 24).attr('refY', 0)
                .attr('markerWidth', 7).attr('markerHeight', 7)
                .attr('orient', 'auto')
                .append('path')
                .attr('d', 'M0,-5L10,0L0,5')
                .attr('fill', linkColors[type]);
        });

        var simulation = d3.forceSimulation(data.nodes)
            .force('link', d3.forceLink(data.links).id(function(d) { return d.id; }).distance(160))
            .force('charge', d3.forceManyBody().strength(-350))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(70));

        // Links
        var link = g.append('g').selectAll('line').data(data.links).join('line')
            .attr('stroke', function(d) { return linkColors[d.type] || '#64748b'; })
            .attr('stroke-width', 2)
            .attr('marker-end', function(d) { return 'url(#pq-arrow-' + (d.type || 'reference') + ')'; });

        // Link labels
        var linkLabel = g.append('g').selectAll('text').data(data.links).join('text')
            .attr('font-size', 9).attr('fill', text2Color).attr('text-anchor', 'middle')
            .text(function(d) { return d.type === 'reference' ? 'ref' : d.type; });

        // Node groups
        var node = g.append('g').selectAll('g').data(data.nodes).join('g')
            .call(d3.drag()
                .on('start', function(e) { if (!e.active) simulation.alphaTarget(0.3).restart(); e.subject.fx = e.subject.x; e.subject.fy = e.subject.y; })
                .on('drag', function(e) { e.subject.fx = e.x; e.subject.fy = e.y; })
                .on('end', function(e) { if (!e.active) simulation.alphaTarget(0); e.subject.fx = null; e.subject.fy = null; }));

        node.append('rect')
            .attr('width', 130).attr('height', 44).attr('x', -65).attr('y', -22).attr('rx', 8)
            .attr('fill', function(d) { return nodeColors[d.type] || '#3b82f6'; })
            .attr('fill-opacity', 0.15)
            .attr('stroke', function(d) { return nodeColors[d.type] || '#3b82f6'; })
            .attr('stroke-width', 1.5);

        node.append('text')
            .attr('text-anchor', 'middle').attr('dy', -3).attr('fill', textColor)
            .attr('font-size', 11).attr('font-weight', 600)
            .text(function(d) { return d.name.length > 18 ? d.name.substring(0, 16) + '..' : d.name; });

        node.append('text')
            .attr('text-anchor', 'middle').attr('dy', 12).attr('fill', text2Color).attr('font-size', 9)
            .text(function(d) {
                var label = d.source_type || d.type;
                return label + (d.step_count ? ' | ' + d.step_count + ' steps' : '');
            });

        node.append('title')
            .text(function(d) { return d.name + '\nType: ' + d.type + (d.source_type ? '\nSource: ' + d.source_type : '') + '\nSteps: ' + d.step_count; });

        simulation.on('tick', function() {
            link.attr('x1', function(d) { return d.source.x; }).attr('y1', function(d) { return d.source.y; })
                .attr('x2', function(d) { return d.target.x; }).attr('y2', function(d) { return d.target.y; });
            linkLabel.attr('x', function(d) { return (d.source.x + d.target.x) / 2; })
                     .attr('y', function(d) { return (d.source.y + d.target.y) / 2 - 6; });
            node.attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
        });

        // Zoom controls
        var controls = d3.select('#' + containerId).append('div')
            .style('position', 'absolute').style('top', '10px').style('right', '10px').style('display', 'flex').style('gap', '4px');
        controls.append('button').attr('class', 'btn-ghost btn-sm').html('<i class="bi bi-zoom-in"></i>')
            .on('click', function() { svg.transition().call(zoom.scaleBy, 1.3); });
        controls.append('button').attr('class', 'btn-ghost btn-sm').html('<i class="bi bi-zoom-out"></i>')
            .on('click', function() { svg.transition().call(zoom.scaleBy, 0.7); });
        controls.append('button').attr('class', 'btn-ghost btn-sm').html('<i class="bi bi-arrows-fullscreen"></i>')
            .on('click', function() { svg.transition().call(zoom.transform, d3.zoomIdentity); });
    };
})();
