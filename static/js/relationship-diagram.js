// Interactive Relationship Diagram - D3.js force-directed graph
(function() {
    'use strict';

    window.renderRelationshipDiagram = function(containerId, graphData) {
        if (!graphData || !graphData.nodes || graphData.nodes.length === 0) return;

        var container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';

        var width = container.clientWidth || 900;
        var height = 550;

        // Theme colors
        var style = getComputedStyle(document.documentElement);
        var textColor = style.getPropertyValue('--text-1').trim() || '#f0f2f5';
        var text2Color = style.getPropertyValue('--text-2').trim() || '#a0aec0';
        var accentColor = style.getPropertyValue('--accent').trim() || '#00bfff';
        var bgCard = style.getPropertyValue('--bg-card').trim() || 'rgba(14,18,38,0.7)';
        var borderColor = style.getPropertyValue('--glass-border').trim() || 'rgba(100,180,255,0.10)';

        var svg = d3.select('#' + containerId)
            .append('svg')
            .attr('width', width)
            .attr('height', height)
            .attr('viewBox', [0, 0, width, height]);

        // Zoom
        var g = svg.append('g');
        var zoom = d3.zoom()
            .scaleExtent([0.3, 4])
            .on('zoom', function(event) {
                g.attr('transform', event.transform);
            });
        svg.call(zoom);

        // Arrow markers
        var defs = svg.append('defs');
        ['normal', 'bidir', 'm2m', 'inactive'].forEach(function(type) {
            var colors = { normal: '#64748b', bidir: '#f87171', m2m: '#fb923c', inactive: '#64748b' };
            defs.append('marker')
                .attr('id', 'arrow-' + type)
                .attr('viewBox', '0 -5 10 10')
                .attr('refX', 28)
                .attr('refY', 0)
                .attr('markerWidth', 8)
                .attr('markerHeight', 8)
                .attr('orient', 'auto')
                .append('path')
                .attr('d', 'M0,-5L10,0L0,5')
                .attr('fill', colors[type]);
        });

        // Force simulation
        var simulation = d3.forceSimulation(graphData.nodes)
            .force('link', d3.forceLink(graphData.links).id(function(d) { return d.id; }).distance(180))
            .force('charge', d3.forceManyBody().strength(-400))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(60));

        // Link type colors
        function linkColor(d) {
            if (!d.is_active) return '#64748b';
            if (d.cross_filtering === 'bothDirections') return '#f87171';
            if (d.from_cardinality === 'many' && d.to_cardinality === 'many') return '#fb923c';
            return '#64748b';
        }

        function linkType(d) {
            if (!d.is_active) return 'inactive';
            if (d.cross_filtering === 'bothDirections') return 'bidir';
            if (d.from_cardinality === 'many' && d.to_cardinality === 'many') return 'm2m';
            return 'normal';
        }

        // Links
        var link = g.append('g')
            .selectAll('line')
            .data(graphData.links)
            .join('line')
            .attr('stroke', linkColor)
            .attr('stroke-width', 2)
            .attr('stroke-dasharray', function(d) { return d.is_active ? null : '6,4'; })
            .attr('marker-end', function(d) { return 'url(#arrow-' + linkType(d) + ')'; });

        // Link labels (cardinality)
        var linkLabel = g.append('g')
            .selectAll('text')
            .data(graphData.links)
            .join('text')
            .attr('font-size', 10)
            .attr('fill', text2Color)
            .attr('text-anchor', 'middle')
            .text(function(d) { return d.from_cardinality + ':' + d.to_cardinality; });

        // Node groups
        var node = g.append('g')
            .selectAll('g')
            .data(graphData.nodes)
            .join('g')
            .call(d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended));

        // Node rectangles
        node.append('rect')
            .attr('width', 120)
            .attr('height', 44)
            .attr('x', -60)
            .attr('y', -22)
            .attr('rx', 10)
            .attr('fill', bgCard)
            .attr('stroke', borderColor)
            .attr('stroke-width', 1.5);

        // Table name
        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', -4)
            .attr('fill', textColor)
            .attr('font-size', 11)
            .attr('font-weight', 600)
            .text(function(d) { return d.name.length > 16 ? d.name.substring(0, 14) + '..' : d.name; });

        // Column/measure counts
        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', 12)
            .attr('fill', text2Color)
            .attr('font-size', 9)
            .text(function(d) { return d.columns + ' cols, ' + d.measures + ' measures'; });

        // Tooltip
        node.append('title')
            .text(function(d) { return d.name + '\n' + d.columns + ' columns, ' + d.measures + ' measures'; });

        // Tick update
        simulation.on('tick', function() {
            link
                .attr('x1', function(d) { return d.source.x; })
                .attr('y1', function(d) { return d.source.y; })
                .attr('x2', function(d) { return d.target.x; })
                .attr('y2', function(d) { return d.target.y; });

            linkLabel
                .attr('x', function(d) { return (d.source.x + d.target.x) / 2; })
                .attr('y', function(d) { return (d.source.y + d.target.y) / 2 - 6; });

            node.attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
        });

        function dragstarted(event) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }

        function dragged(event) {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }

        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }

        // Zoom controls
        var controls = d3.select('#' + containerId)
            .append('div')
            .style('position', 'absolute')
            .style('top', '10px')
            .style('right', '10px')
            .style('display', 'flex')
            .style('gap', '4px');

        controls.append('button')
            .attr('class', 'btn-ghost btn-sm')
            .html('<i class="bi bi-zoom-in"></i>')
            .on('click', function() { svg.transition().call(zoom.scaleBy, 1.3); });

        controls.append('button')
            .attr('class', 'btn-ghost btn-sm')
            .html('<i class="bi bi-zoom-out"></i>')
            .on('click', function() { svg.transition().call(zoom.scaleBy, 0.7); });

        controls.append('button')
            .attr('class', 'btn-ghost btn-sm')
            .html('<i class="bi bi-arrows-fullscreen"></i>')
            .on('click', function() { svg.transition().call(zoom.transform, d3.zoomIdentity); });
    };
})();
